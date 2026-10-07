# Deployment

Prometheus is served at **https://prometheus.thaiv.dev** from AWS, through the `thaiv.dev` platform defined in `~/repos/project-platform-infrastructure` (AWS CDK).

## Infrastructure (owned by project-platform-infrastructure)

- Stack `ThaivPrometheusProject` (`us-west-2`): a private, versioned S3 bucket behind CloudFront with origin path `/current`, the shared `*.thaiv.dev` wildcard certificate, Route 53 A/AAAA aliases, `/404.html` served for missing paths (status 404), and lifecycle rules (since 2026-10-07, infra PR #14): `releases/` expires after 14 days, noncurrent versions after 30, incomplete multipart uploads after 1.
- Deploy access: the shared GitHub OIDC role from `ThaivProjectPlatform` (any `thaiv28/*` repo on `main`), granted this bucket and distribution through the managed policy `thaiv-prometheus-static-deployment`.
- Infrastructure changes are made in that repo and deployed with its **Deploy Prometheus Infrastructure** workflow (`diff`, then `deploy`). That workflow only touches this stack.

## Publishing (this repo)

`.github/workflows/publish.yml` runs on push to `main`, daily at 10:00 UTC, on manual dispatch, and as a build-only check on pull requests:

1. `check` (every run, before any data): `uv sync` (with the dev group), `ruff format --check`, `ruff check`, and `pytest` (the e2e tests build a small DB from the committed CSV sample, so no download is needed). `build` waits for it.
2. `build`: `uv sync`, restore the CSV cache, `scripts/setup_db.sh` (downloads Oracle's Elixir CSVs and rebuilds the DB), the e2e tests again on the full DB (`PROMETHEUS_E2E_DB=real pytest -m e2e`), `scripts/evaluate_metrics.py --check-weights` (refits the Form and FORGE weights, about 8 seconds, prints every change, and adds a warning annotation, not a failure, if a FORGE blend weight moved more than 10%), restore the prediction log from the backup bucket (main only), `scripts/build_site.py` (which fetches the match schedule from Leaguepedia and updates the log), save the log back, then upload `output/` as an artifact.
3. `deploy` (on `main` only, and only once the repo variables exist): assume `AWS_ROLE_ARN`, run `scripts/deploy_site.py` on the build's artifact, invalidate CloudFront (`/*`), and health-check the site.

### Uploads (`scripts/deploy_site.py`, since 2026-10-07)

The deploy writes straight into `s3://$DEPLOYMENT_BUCKET/current/` and sends only files whose content changed. `s3://$DEPLOYMENT_BUCKET/deploy/manifest.json` (outside `current/`, so not served) holds the SHA-256 of every file of the last deploy. Each run hashes `output/`, uploads the changed and new files, deletes the removed ones, re-uploads `kalshi.json` and `predictions.json` with `Cache-Control: max-age=300` every time (see *Hourly Kalshi prices*), and writes the new manifest. The manifest is deleted before any file changes and written only after the upload succeeds, so a failed run leaves none and the next run uploads every file (`aws s3 cp --recursive`, then `aws s3 sync --delete` to remove leftovers). Dispatch the workflow with **full_upload** checked to force that. `aws s3 sync` alone can't skip unchanged files: it compares size and timestamp, and every artifact download is new.

Pages carry no build date (the footer's "Last updated" was removed; only the home page's title line has it), so a page changes only when its content does. Before this, each deploy uploaded all ~11,200 files to `releases/<run id>` and then copied them into `current/` (~22k requests, ~6 of a push run's ~10 minutes).

The game-log JSON (~110 MB) is uploaded uncompressed: CloudFront's `CachingOptimized` policy already compresses JSON at the edge, and with changed-only uploads most of it isn't re-sent.

Runs share a concurrency group per ref (`deploy-prometheus-<ref>`; a PR's ref is `refs/pull/<n>/merge`). A new push to a PR cancels that PR's run in progress; runs on `main` (push, schedule, dispatch) are never cancelled and queue instead. PR runs never wait on or cancel a main publish.

This mirrors the shared `thaiv28/project-platform-workflows` `deploy-static.yml`, which can't be reused directly because it builds with npm.

CSS and JS links carry a content-hash query (`?v=`, from `asset()` in `build_site.py`), so a deploy that changes them reaches browsers that cached the old files; the CloudFront invalidation only clears the edge.

Required repository settings:

| Kind | Name | Source |
|---|---|---|
| Variable | `DEPLOYMENT_BUCKET` | `ThaivPrometheusProject` output `DeploymentBucket` |
| Variable | `CLOUDFRONT_DISTRIBUTION_ID` | `ThaivPrometheusProject` output `CloudFrontDistributionId` |
| Secret | `AWS_ROLE_ARN` | `ThaivProjectPlatform` output `DeploymentRoleArn` |
| Variable | `DATA_BACKUP_BUCKET` | `ThaivProjectPlatform` `PlatformArtifacts` bucket |
| Secret (optional) | `LEAGUEPEDIA_USER`, `LEAGUEPEDIA_PASSWORD` | A Leaguepedia bot password (Special:BotPasswords on lol.fandom.com, read access only). Logged-in clients get a much higher rate limit; without them the build reads the schedule anonymously and, if refused, keeps yesterday's calls. Set 2026-10-06; local builds read the same two values from a gitignored `.env`. |
| Env (optional) | `KALSHI_PRICES` | Set to `0` to skip reading Kalshi's prices at build time (the Predictions page then keeps the prices already in the log). Unset in CI: each build makes one unauthenticated call to Kalshi's public API. |
| Env (optional) | `KALSHI_ALERTS` | Set to `0` to skip the alerts. Otherwise a build or hourly run that priced matches writes `data/kalshi_alert.json` when FORGE beats Kalshi's ask by 5+ points on a match 6–36 hours out, and `scripts/post_kalshi_alert.sh` (the *Post the Kalshi alert* step in both workflows; main only, `issues: write`, the workflow's own token, `continue-on-error`) creates the day's `kalshi-alert` issue mentioning the owner (closing earlier ones), or edits it in place and comments only for new matches. GitHub's notification email is the alert. |

## Data backup

Google Drive rate-limits the shared Oracle's Elixir CSVs. Each build tries Drive first, falling back to the Actions cache and then, on `main`, to gzipped copies in `s3://$DATA_BACKUP_BUCKET/prometheus/oracles-elixir/`. A successful Drive download is synced back there, so the backup always holds the newest good data. PR builds can't assume the AWS role, so they rely on the cache that `main` builds save. With no data from any source, the build fails rather than publishing an empty site.

The Actions cache (about 200 MB an entry; GitHub keeps 10 GB a repo and evicts entries unused for 7 days): every build restores the newest `oracles-elixir-*` entry before `setup_db.sh` (`actions/cache/restore`). Only `main` builds save, after `setup_db.sh`, keyed on the CSVs' content (`oracles-elixir-<hashFiles('data/raw/*.csv')>`), and only when that key differs from the one restored, so a day whose download is unchanged (or failed) adds nothing. That keeps about one entry per day of new data. Until 2026-10-07 every run, PRs included, saved a new entry keyed on the run id, which passed the 10 GB limit.

## Prediction log

`s3://$DATA_BACKUP_BUCKET/prometheus/predictions/predictions.json` holds every call saved before its match and the results (the deploy role has read-write on the whole bucket). Main builds restore it before `build_site.py` and copy it back after, so calls accumulate across days; PR builds can't reach it and start a fresh log (with a 30-day reconstructed backfill) that is thrown away. If the file is lost, the next build starts a new log and the "saved before the match" record restarts from that day. The site is rebuilt once a day (10:00 UTC), so a match's saved call uses the data through the previous day.

## Kalshi prices

`s3://$DATA_BACKUP_BUCKET/prometheus/markets/market_prices.json` holds Kalshi's last price before each past series, for the game logs on team and player pages. Main builds restore it before `build_site.py` (read-only; the build never writes it). It is refreshed by hand: run `scripts/evaluate_markets.py` (slow, fetches Kalshi), then `scripts/export_market_prices.py`, then `aws s3 cp data/market_prices.json s3://$DATA_BACKUP_BUCKET/prometheus/markets/market_prices.json`. Without it, logs show only the prices saved in the prediction log.

## Notes

- **Rolling back.** Within 7 days (the artifact's retention), re-run the `deploy` job of the earlier run (Actions → that run → Re-run jobs → `deploy`, or `gh run rerun <run id> --job <deploy job id>`): it uploads the differences between that run's site and the manifest, then invalidates. Older than that, revert the commit and let the publish rebuild (today's data, the old code), or restore objects from S3 versions (the bucket is versioned) and then delete `deploy/manifest.json` so the next deploy uploads everything. Do the same after any change to `current/` made outside `deploy_site.py`, including re-running a deploy from before 2026-10-07 (it used `releases/`).
- `releases/` is no longer written. The old releases (about 290 MB each since 2026-10-06; 7.4 GB in the bucket on 6 Oct) expire under the lifecycle rule 14 days after they were written, and their noncurrent versions 30 days after that; no manual delete is needed. S3-version rollback therefore reaches back 30 days.
- GitHub disables scheduled workflows after 60 days without repository activity. If the daily rebuild stops, re-enable it under Actions.
- The old GitHub Pages site (`thaiv28.github.io/Prometheus`) should be turned off once the AWS site is live.

## Hourly Kalshi prices (`.github/workflows/prices.yml`)

- Runs at :17 every hour and on manual dispatch; main only; about a minute. Installs with `uv sync --frozen --no-dev` (no ruff or pytest).
- **External trigger (since 2026-10-06).** GitHub's scheduler is best effort: on 6 Oct it started this hourly job once in about 12 hours, and the daily publish (10:00 UTC) starts 4–9 hours late most days. A cron-job.org job (account owned by the repo owner) POSTs `https://api.github.com/repos/thaiv28/Prometheus/actions/workflows/prices.yml/dispatches` with body `{"ref":"main"}` every hour at :17, authenticated with a fine-grained personal access token limited to this repository with only *Actions: read and write*. Dispatched runs start at once. The GitHub schedule stays as a backup; a duplicate run is harmless (concurrency group `kalshi-prices` runs them in turn). If prices stop updating, check the cron-job.org job's history (a 401/403 means the token expired or lost its permission; renew it and update the job's `Authorization: Bearer` header).
- Skips the hour while a publish run is queued or running: both read and write the prediction log, and publish holds it for several minutes between restore and save. The hourly job finishes well before a publish that starts after it restores the log.
- Steps: restore `data/predictions.json` from the backup bucket, `scripts/update_prices.py`, save the log back, copy `kalshi.json` and `predictions.json` into the site bucket's `current/` with `Cache-Control: max-age=300`, then post the alert.
- No CloudFront invalidation (since 2026-10-07): two paths an hour is about 1,440 a month, over the free 1,000. The distribution uses the managed `CachingOptimized` policy (`static-project-stack.ts` in the infrastructure repo: min TTL 1 s, default 1 day, max 1 year), which honours the object's `max-age=300`, so the edge serves the new files within 5 minutes. The publish deploy re-uploads both with the same header on every run, because a plain upload carries no `Cache-Control` and would get the 1-day default. `predictions.js` fetches `kalshi.json` with `cache: "no-store"`, which skips the browser cache but not CloudFront's, so a page sees prices at most about 5 minutes behind the job; `predictions.json` is only a link and may sit in a browser's cache for 5 minutes.
- Uses the same role as the publish workflow (`AWS_ROLE_ARN`: backup bucket read-write, site bucket write) and the `DATA_BACKUP_BUCKET` and `DEPLOYMENT_BUCKET` variables.
