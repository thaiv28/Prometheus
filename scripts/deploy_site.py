"""Upload the built site to the bucket's `current/` prefix, sending only changed files.

CloudFront serves `s3://$BUCKET/current`. A content-hash manifest of the last deploy
lives outside it, at `s3://$BUCKET/deploy/manifest.json`. Each deploy hashes
`output/`, uploads the files whose hash changed or that are new, deletes the ones
that are gone, and writes the new manifest. With no manifest (the first run, after
a failed run, or `--full`) it uploads every file and deletes the rest.

The manifest is deleted before any file changes and written back only after the
upload succeeds, so a run that fails partway leaves no manifest and the next run
uploads everything: `current/` never differs from what the manifest says.

`kalshi.json` and `predictions.json` are always uploaded, with a 5-minute
Cache-Control, because the hourly prices job rewrites them in `current/` between
deploys (see docs/steering/deployment.md). CSS and JS get a year and `immutable`
(every page links them with a content-hash `?v=`, so a change is a new URL to the
browser; the deploy's CloudFront invalidation clears the edge), fonts 30 days;
everything else gets none, and CloudFront's default applies.

    BUCKET=... python3 scripts/deploy_site.py [--output output] [--full] [--dry-run]

Needs the AWS CLI and credentials that can write the bucket. Standard library only.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
MANIFEST_KEY = "deploy/manifest.json"
SITE_PREFIX = "current"
HOURLY_FILES = ("kalshi.json", "predictions.json")
HOURLY_CACHE_CONTROL = "max-age=300"
LONG_CACHE = {
    ".css": "public, max-age=31536000, immutable",
    ".js": "public, max-age=31536000, immutable",
    ".woff2": "public, max-age=2592000",
}


def cache_control(path):
    """The Cache-Control a site file is uploaded with, or None for the default."""
    return LONG_CACHE.get(Path(path).suffix)


def build_manifest(root):
    """{relative path: sha256} for every file under root, with '/' separators."""
    manifest = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            manifest[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return manifest


def plan(old, new, always=HOURLY_FILES):
    """Files to upload and keys to delete, going from manifest `old` to `new`.

    Files in `always` are left out of both lists (they're uploaded separately).
    """
    upload = sorted(p for p, h in new.items() if p not in always and old.get(p) != h)
    delete = sorted(p for p in old if p not in new and p not in always)
    return upload, delete


def aws(*args, capture=False, dry_run=False):
    if dry_run:
        print("+ aws", " ".join(args))
        return ""
    result = subprocess.run(
        ["aws", *args], check=True, text=True, capture_output=capture
    )
    return result.stdout if capture else ""


def read_manifest(bucket):
    """The last deploy's manifest, or None if there isn't one."""
    try:
        text = aws(
            "s3",
            "cp",
            f"s3://{bucket}/{MANIFEST_KEY}",
            "-",
            "--only-show-errors",
            capture=True,
        )
    except subprocess.CalledProcessError:
        return None
    return json.loads(text) if text.strip() else None


def upload_files(output, bucket, paths, dry_run):
    """Copy `paths` (relative to output) into a staging tree and upload it, one
    `aws s3 cp --recursive` per Cache-Control value."""
    groups = {}
    for rel in paths:
        groups.setdefault(cache_control(rel), []).append(rel)
    for header, group in sorted(groups.items(), key=lambda g: g[0] or ""):
        with tempfile.TemporaryDirectory() as staging:
            for rel in group:
                dest = Path(staging) / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(output / rel, dest)
                except OSError:
                    shutil.copy2(output / rel, dest)
            aws(
                "s3",
                "cp",
                staging,
                f"s3://{bucket}/{SITE_PREFIX}",
                "--recursive",
                "--only-show-errors",
                *(["--cache-control", header] if header else []),
                dry_run=dry_run,
            )


def delete_keys(bucket, paths, dry_run):
    for start in range(0, len(paths), 1000):
        chunk = paths[start : start + 1000]
        objects = [{"Key": f"{SITE_PREFIX}/{p}"} for p in chunk]
        aws(
            "s3api",
            "delete-objects",
            "--bucket",
            bucket,
            "--delete",
            json.dumps({"Objects": objects, "Quiet": True}),
            dry_run=dry_run,
        )


def upload_hourly_files(output, bucket, dry_run):
    for name in HOURLY_FILES:
        if (output / name).is_file():
            aws(
                "s3",
                "cp",
                str(output / name),
                f"s3://{bucket}/{SITE_PREFIX}/{name}",
                "--only-show-errors",
                "--content-type",
                "application/json",
                "--cache-control",
                HOURLY_CACHE_CONTROL,
                dry_run=dry_run,
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--full", action="store_true", help="sync every file, ignoring the manifest"
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT, help="the built site (default output/)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the AWS commands instead of running them",
    )
    args = parser.parse_args(argv)
    output = args.output.resolve()
    bucket = os.environ["BUCKET"]
    if not (output / "index.html").is_file():
        sys.exit(f"{output} has no index.html; build the site first")

    new = build_manifest(output)
    old = None if args.full else read_manifest(bucket)
    # No manifest while files change: a run that dies here leaves the next one a full sync.
    aws(
        "s3",
        "rm",
        f"s3://{bucket}/{MANIFEST_KEY}",
        "--only-show-errors",
        dry_run=args.dry_run,
    )
    if old is None:
        print(f"Full upload of {len(new):,} files")
        # `s3 sync` skips a file whose size matches and whose local copy is older,
        # so copy everything, then sync only to delete what the site no longer has.
        site = f"s3://{bucket}/{SITE_PREFIX}"
        aws(
            "s3",
            "cp",
            str(output),
            site,
            "--recursive",
            "--only-show-errors",
            dry_run=args.dry_run,
        )
        aws(
            "s3",
            "sync",
            str(output),
            site,
            "--delete",
            "--only-show-errors",
            dry_run=args.dry_run,
        )
        # The copy above sets no Cache-Control; send the long-cached files again.
        upload_files(output, bucket, [p for p in new if cache_control(p)], args.dry_run)
    else:
        upload, delete = plan(old, new)
        print(
            f"{len(upload):,} changed or new, {len(delete):,} removed, "
            f"{len(new) - len(upload):,} unchanged"
        )
        upload_files(output, bucket, upload, args.dry_run)
        delete_keys(bucket, delete, args.dry_run)
    upload_hourly_files(output, bucket, args.dry_run)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(new, f, separators=(",", ":"))
    try:
        aws(
            "s3",
            "cp",
            f.name,
            f"s3://{bucket}/{MANIFEST_KEY}",
            "--only-show-errors",
            "--content-type",
            "application/json",
            dry_run=args.dry_run,
        )
    finally:
        os.unlink(f.name)


if __name__ == "__main__":
    main()
