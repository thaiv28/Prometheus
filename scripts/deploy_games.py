"""Upload hash-changed Other games files with a separate, failure-safe manifest.

The main publish deploy also writes other/ from its own build; both upload by
hash, so the newer content wins within one cycle. No edge invalidation is needed.
"""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from deploy_site import aws, build_manifest, delete_keys, plan, upload_files

OUTPUT = Path(__file__).resolve().parent.parent / "output"
MANIFEST_KEY = "deploy/other-manifest.json"
PREFIX = "current/other"
CACHE_CONTROL = "public, max-age=60"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    output = args.output / "other"
    if not output.is_dir():
        parser.error(f"{output} is missing; render games first")
    bucket = os.environ["DEPLOYMENT_BUCKET"]
    manifest_url = f"s3://{bucket}/{MANIFEST_KEY}"
    new = build_manifest(output)
    try:
        old = json.loads(
            aws("s3", "cp", manifest_url, "-", "--only-show-errors", capture=True)
        )
    except (subprocess.CalledProcessError, ValueError):
        old = None
    upload, delete = plan(old or {}, new, always=())
    aws("s3", "rm", manifest_url, "--only-show-errors", dry_run=args.dry_run)
    upload_files(
        output, bucket, upload, args.dry_run, prefix=PREFIX, header=CACHE_CONTROL
    )
    if old is None:
        # Recover leftovers from a failed deploy, scoped strictly to other/.
        aws(
            "s3",
            "sync",
            str(output),
            f"s3://{bucket}/{PREFIX}",
            "--delete",
            "--only-show-errors",
            "--cache-control",
            CACHE_CONTROL,
            dry_run=args.dry_run,
        )
    else:
        delete_keys(bucket, delete, args.dry_run, prefix=PREFIX)
    with tempfile.TemporaryDirectory() as staging:
        manifest = Path(staging) / "manifest.json"
        manifest.write_text(json.dumps(new, separators=(",", ":")))
        aws(
            "s3",
            "cp",
            str(manifest),
            manifest_url,
            "--only-show-errors",
            "--content-type",
            "application/json",
            dry_run=args.dry_run,
        )
    summary = f"Other games: {len(upload)} files uploaded, {len(delete)} removed"
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(summary + "\n")


if __name__ == "__main__":
    main()
