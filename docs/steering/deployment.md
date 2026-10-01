# Deployment

## Current

GitHub Pages via `.github/workflows/static.yml`:

1. `uv sync --frozen && uv pip install -e .`
2. `uv run bash scripts/setup_db.sh`, which downloads the CSVs and builds the DB
3. `uv run python scripts/build_site.py`, which writes to `output/`
4. Upload `./output` as the Pages artifact and deploy

Triggers: push to `main`, daily cron at 10:00 UTC, and manual dispatch.

The git remote is `thaiv28/LeagueOfMetrics`, but the site footer links to `thaiv28/Prometheus`. Reconcile these when moving domains.

## Target: prometheus.thaiv.dev

Plan (GitHub Pages with a custom domain):

1. Have `build_site.py` write `output/CNAME` containing `prometheus.thaiv.dev`. Alternatively, set the domain in repo Settings → Pages. With the Actions-based deploy, the Settings value is authoritative, and a CNAME file is harmless.
2. DNS at the `thaiv.dev` registrar: add `CNAME prometheus → thaiv28.github.io`.
3. Optionally verify `thaiv.dev` under GitHub account settings → Pages, to prevent domain takeover.
4. Enable **Enforce HTTPS** after the certificate is issued. `.dev` is HSTS-preloaded, so the site won't load at all over plain HTTP.
5. All asset paths are relative (`root_path`), so serving from the domain root works without template changes.

## Pre-launch checklist

- [x] Fix the reflected XSS via `?search=` (all JS output now goes through `esc()`)
- [x] Add a favicon, `<meta name="description">`, and Open Graph tags
- [ ] Add a 404 page
- [x] Set the canonical URL to `https://prometheus.thaiv.dev` (`SITE_URL` in `build_site.py`)
- [x] Fix the Elo bootstrap bugs (rating lookups, loss scoring, duplicate rows)
- [ ] Commit the Elo work and the redesign
