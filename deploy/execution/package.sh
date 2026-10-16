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
cp "$root/prometheus/market_blend.py" "$root/prometheus/market_blend.json" "$stage/prometheus/"
cp -R "$root/prometheus/execution" "$stage/prometheus/execution"
cp "$root/deploy/execution/handler.py" "$stage/deploy/execution/handler.py"
# Export the existing literal alias map without importing the site's pandas/API
# modules. One source of truth; exact aliases only, never fuzzy matching.
uv run --no-project python - "$root/prometheus/markets.py" "$stage/deploy/execution/market_aliases.json" <<'ALIASES'
import ast
import json
import pathlib
import sys
module = ast.parse(pathlib.Path(sys.argv[1]).read_text())
assignment = next(node for node in module.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "MARKET_ALIASES" for target in node.targets))
pathlib.Path(sys.argv[2]).write_text(json.dumps(ast.literal_eval(assignment.value), sort_keys=True))
ALIASES
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
