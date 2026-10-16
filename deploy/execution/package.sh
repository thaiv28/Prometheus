#!/usr/bin/env bash
# Build only; never uploads, deploys, reads credentials or changes mode.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
target="${1:?Pass an output zip path}"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
uv run --no-project --python 3.12 --with pip python -m pip install \
  --disable-pip-version-check --no-compile --only-binary=:all: \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
  --target "$stage" -r "$root/deploy/execution/requirements.txt"
mkdir -p "$stage/prometheus" "$stage/deploy/execution"
cp "$root/prometheus/__init__.py" "$root/prometheus/alert_contract.py" "$stage/prometheus/"
cp -R "$root/prometheus/execution" "$stage/prometheus/execution"
cp "$root/deploy/execution/handler.py" "$stage/deploy/execution/handler.py"
# Drop local bytecode and all account/config inputs. Only a tiny allowlist enters.
uv run --no-project python - "$stage" "$target" <<'PYTHON'
import pathlib
import sys
import zipfile
stage, target = map(pathlib.Path, sys.argv[1:])
target.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(stage.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and path.relative_to(stage).parts[0] != "bin":
            archive.write(path, path.relative_to(stage))
print(target)
PYTHON
