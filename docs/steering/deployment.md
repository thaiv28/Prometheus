# Deployment

Prometheus is served at **https://prometheus.thaiv.dev** from AWS, through the `thaiv.dev` platform defined in `~/repos/project-platform-infrastructure` (AWS CDK).

## Infrastructure (owned by project-platform-infrastructure)

- Stack `ThaivPrometheusProject` (`us-west-2`): a private, versioned S3 bucket behind CloudFront with origin path `/current`, the shared `*.thaiv.dev` wildcard certificate, Route 53 A/AAAA aliases, and `/404.html` served for missing paths (status 404).
- Deploy access: the shared GitHub OIDC role from `ThaivProjectPlatform` (any `thaiv28/*` repo on `main`), granted this bucket and distribution through the managed policy `thaiv-prometheus-static-deployment`.
- Infrastructure changes are made in that repo and deployed with its **Deploy Prometheus Infrastructure** workflow (`diff`, then `deploy`). That workflow only touches this stack.

## Publishing (this repo)

`.github/workflows/publish.yml` runs on push to `main`, daily at 10:00 UTC, on manual dispatch, and as a build-only check on pull requests:

1. `build`: `uv sync`, `scripts/setup_db.sh` (downloads Oracle's Elixir CSVs and rebuilds the DB), `pytest`, `scripts/evaluate_metrics.py --check-weights` (refits the Form and FORGE weights, about 8 seconds, prints every change, and adds a warning annotation, not a failure, if a FORGE blend weight moved more than 10%), restore the prediction log from the backup bucket (main only), `scripts/build_site.py` (which fetches the match schedule from Leaguepedia and updates the log), save the log back, then upload `output/` as an artifact.
2. `deploy` (on `main` only, and only once the repo variables exist): assume `AWS_ROLE_ARN`, sync to `s3://$DEPLOYMENT_BUCKET/releases/<run id>`, sync that release to `/current`, invalidate CloudFront, and health-check the site.

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

## Prediction log

`s3://$DATA_BACKUP_BUCKET/prometheus/predictions/predictions.json` holds every call saved before its match and the results (the deploy role has read-write on the whole bucket). Main builds restore it before `build_site.py` and copy it back after, so calls accumulate across days; PR builds can't reach it and start a fresh log (with a 30-day reconstructed backfill) that is thrown away. If the file is lost, the next build starts a new log and the "saved before the match" record restarts from that day. The site is rebuilt once a day (10:00 UTC), so a match's saved call uses the data through the previous day.

## Kalshi prices

`s3://$DATA_BACKUP_BUCKET/prometheus/markets/market_prices.json` holds Kalshi's last price before each past series, for the game logs on team and player pages. Main builds restore it before `build_site.py` (read-only; the build never writes it). It is refreshed by hand: run `scripts/evaluate_markets.py` (slow, fetches Kalshi), then `scripts/export_market_prices.py`, then `aws s3 cp data/market_prices.json s3://$DATA_BACKUP_BUCKET/prometheus/markets/market_prices.json`. Without it, logs show only the prices saved in the prediction log.

## Notes

- Rolling back means syncing an older `releases/<run id>` prefix to `current` and invalidating.
- Each run adds a full release to `releases/`: about 290 MB since game logs (2026-10-06; 100 MB from 2026-10-02, about 30 MB before). Add an S3 lifecycle rule in the infrastructure stack to expire old releases.
- GitHub disables scheduled workflows after 60 days without repository activity. If the daily rebuild stops, re-enable it under Actions.
- The old GitHub Pages site (`thaiv28.github.io/Prometheus`) should be turned off once the AWS site is live.

## Hourly Kalshi prices (`.github/workflows/prices.yml`)

- Runs at :17 every hour and on manual dispatch; main only; about a minute.
- **External trigger (since 2026-10-06).** GitHub's scheduler is best effort: on 6 Oct it started this hourly job once in about 12 hours, and the daily publish (10:00 UTC) starts 4–9 hours late most days. A cron-job.org job (account owned by the repo owner) POSTs `https://api.github.com/repos/thaiv28/Prometheus/actions/workflows/prices.yml/dispatches` with body `{"ref":"main"}` every hour at :17, authenticated with a fine-grained personal access token limited to this repository with only *Actions: read and write*. Dispatched runs start at once. The GitHub schedule stays as a backup; a duplicate run is harmless (concurrency group `kalshi-prices` runs them in turn). If prices stop updating, check the cron-job.org job's history (a 401/403 means the token expired or lost its permission; renew it and update the job's `Authorization: Bearer` header).
- Skips the hour while a publish run is queued or running: both read and write the prediction log, and publish holds it for several minutes between restore and save. The hourly job finishes well before a publish that starts after it restores the log.
- Steps: restore `data/predictions.json` from the backup bucket, `scripts/update_prices.py`, save the log back, copy `kalshi.json` and `predictions.json` into the site bucket's `current/` (`max-age=300`) and invalidate those two paths, then post the alert.
- Uses the same role as the publish workflow (`AWS_ROLE_ARN`: backup bucket read-write, site bucket write, CloudFront invalidation) and the `DATA_BACKUP_BUCKET`, `DEPLOYMENT_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID` variables.
