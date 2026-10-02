# Deployment

Prometheus is served at **https://prometheus.thaiv.dev** from AWS, through the `thaiv.dev` platform defined in `~/repos/project-platform-infrastructure` (AWS CDK).

## Infrastructure (owned by project-platform-infrastructure)

- Stack `ThaivPrometheusProject` (`us-west-2`): a private, versioned S3 bucket behind CloudFront with origin path `/current`, the shared `*.thaiv.dev` wildcard certificate, Route 53 A/AAAA aliases, and `/404.html` served for missing paths (status 404).
- Deploy access: the shared GitHub OIDC role from `ThaivProjectPlatform` (any `thaiv28/*` repo on `main`), granted this bucket and distribution through the managed policy `thaiv-prometheus-static-deployment`.
- Infrastructure changes are made in that repo and deployed with its **Deploy Prometheus Infrastructure** workflow (`diff`, then `deploy`). That workflow only touches this stack.

## Publishing (this repo)

`.github/workflows/publish.yml` runs on push to `main`, daily at 10:00 UTC, on manual dispatch, and as a build-only check on pull requests:

1. `build`: `uv sync`, `scripts/setup_db.sh` (downloads Oracle's Elixir CSVs and rebuilds the DB), `pytest`, `scripts/evaluate_metrics.py --check-weights` (refits the GlorELO+ weights, about 25 seconds, and adds a warning annotation, not a failure, if one moved more than 10%), `scripts/build_site.py`, then upload `output/` as an artifact.
2. `deploy` (on `main` only, and only once the repo variables exist): assume `AWS_ROLE_ARN`, sync to `s3://$DEPLOYMENT_BUCKET/releases/<run id>`, sync that release to `/current`, invalidate CloudFront, and health-check the site.

This mirrors the shared `thaiv28/project-platform-workflows` `deploy-static.yml`, which can't be reused directly because it builds with npm.

Required repository settings:

| Kind | Name | Source |
|---|---|---|
| Variable | `DEPLOYMENT_BUCKET` | `ThaivPrometheusProject` output `DeploymentBucket` |
| Variable | `CLOUDFRONT_DISTRIBUTION_ID` | `ThaivPrometheusProject` output `CloudFrontDistributionId` |
| Secret | `AWS_ROLE_ARN` | `ThaivProjectPlatform` output `DeploymentRoleArn` |
| Variable | `DATA_BACKUP_BUCKET` | `ThaivProjectPlatform` `PlatformArtifacts` bucket |

## Data backup

Google Drive rate-limits the shared Oracle's Elixir CSVs. Each build tries Drive first, falling back to the Actions cache and then, on `main`, to gzipped copies in `s3://$DATA_BACKUP_BUCKET/prometheus/oracles-elixir/`. A successful Drive download is synced back there, so the backup always holds the newest good data. PR builds can't assume the AWS role, so they rely on the cache that `main` builds save. With no data from any source, the build fails rather than publishing an empty site.

## Notes

- Rolling back means syncing an older `releases/<run id>` prefix to `current` and invalidating.
- Each run adds a full release (about 14 MB) to `releases/`. Add an S3 lifecycle rule in the infrastructure stack if that grows.
- GitHub disables scheduled workflows after 60 days without repository activity. If the daily rebuild stops, re-enable it under Actions.
- The old GitHub Pages site (`thaiv28.github.io/Prometheus`) should be turned off once the AWS site is live.
