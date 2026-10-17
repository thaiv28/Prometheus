"""Fingerprint the isolated executor without importing site dependencies."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def aliases(root=ROOT):
    module = ast.parse((root / "prometheus/markets.py").read_text())
    node = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "MARKET_ALIASES" for t in node.targets
        )
    )
    return json.dumps(ast.literal_eval(node.value), sort_keys=True).encode()


def source_hash(root=ROOT):
    paths = {
        "prometheus/__init__.py",
        "prometheus/alert_contract.py",
        "prometheus/market_blend.py",
        "prometheus/market_blend.json",
        "deploy/execution/handler.py",
        "deploy/execution/package.sh",
        "deploy/execution/requirements.txt",
        "deploy/execution/release.py",
    }
    paths.update(
        str(p.relative_to(root)) for p in (root / "prometheus/execution").glob("*.py")
    )
    digest = hashlib.sha256()
    for name in sorted(paths):
        digest.update(name.encode() + b"\0" + (root / name).read_bytes() + b"\0")
    digest.update(b"market_aliases.json\0" + aliases(root))
    return digest.hexdigest()


def verify_runtime(client, function, expected=None):
    response = client.get_function(FunctionName=function)
    config, tags = response["Configuration"], response.get("Tags", {})
    import base64

    digest = base64.b64decode(config["CodeSha256"]).hex()
    if (
        config.get("State") != "Active"
        or config.get("LastUpdateStatus") != "Successful"
        or tags.get("ExecutionSourceSha256") != (expected or source_hash())
        or tags.get("ExecutionPackageKey")
        != f"prometheus/execution/releases/{digest}.zip"
    ):
        raise ValueError(
            "Deployed executor does not match this release; wait for a successful deployment"
        )
    return response
