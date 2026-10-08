import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "deploy_site", ROOT / "scripts" / "deploy_site.py"
)
deploy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deploy)


def test_manifest_hashes_every_file_by_relative_path(tmp_path):
    (tmp_path / "teams").mkdir()
    (tmp_path / "index.html").write_text("home")
    (tmp_path / "teams" / "t1.html").write_text("t1")

    manifest = deploy.build_manifest(tmp_path)

    assert set(manifest) == {"index.html", "teams/t1.html"}
    assert manifest["index.html"] != manifest["teams/t1.html"]
    (tmp_path / "teams" / "t1.html").write_text("t1")  # same content, new mtime
    assert deploy.build_manifest(tmp_path) == manifest


def test_plan_uploads_changed_and_new_and_deletes_removed():
    old = {"a.html": "1", "b.html": "2", "gone.html": "3", "kalshi.json": "k"}
    new = {"a.html": "1", "b.html": "changed", "new.html": "4", "kalshi.json": "k2"}

    upload, delete = deploy.plan(old, new)

    # kalshi.json is uploaded on every deploy, apart from the plan.
    assert upload == ["b.html", "new.html"]
    assert delete == ["gone.html"]


def _fake_aws(monkeypatch, manifest=None):
    calls = []

    def aws(*args, capture=False, dry_run=False):
        calls.append(args)
        if args[:2] == ("s3", "cp") and args[-2:] == ("-", "--only-show-errors"):
            if manifest is None:
                raise deploy.subprocess.CalledProcessError(1, "aws")
            return json.dumps(manifest)
        return ""

    monkeypatch.setattr(deploy, "aws", aws)
    return calls


@pytest.fixture
def site(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("home")
    (tmp_path / "kalshi.json").write_text("{}")
    monkeypatch.setenv("BUCKET", "site-bucket")
    return tmp_path


def test_without_a_manifest_everything_is_uploaded(site, monkeypatch):
    calls = _fake_aws(monkeypatch, manifest=None)

    deploy.main(["--output", str(site)])

    verbs = [c[:2] for c in calls]
    rm = verbs.index(("s3", "rm"))
    # The old manifest goes before any file changes; the new one is written last.
    assert ("s3", "sync") in verbs[rm:]
    assert calls[-1][3] == "s3://site-bucket/deploy/manifest.json"


def test_with_a_manifest_only_changed_files_are_sent(site, monkeypatch):
    unchanged = deploy.build_manifest(site)
    calls = _fake_aws(monkeypatch, manifest=unchanged | {"old.html": "x"})

    deploy.main(["--output", str(site)])

    verbs = [c[:2] for c in calls]
    assert ("s3", "sync") not in verbs
    # Nothing changed, so no bulk upload; old.html is deleted; kalshi.json is re-sent.
    assert not any(c[:2] == ("s3", "cp") and "--recursive" in c for c in calls)
    (delete,) = [c for c in calls if c[:2] == ("s3api", "delete-objects")]
    assert json.loads(delete[-1])["Objects"] == [{"Key": "current/old.html"}]
    assert any(c[-1] == "max-age=300" and c[2].endswith("kalshi.json") for c in calls)


def test_css_js_and_fonts_go_up_with_long_cache_headers(site, monkeypatch):
    (site / "css").mkdir()
    (site / "css" / "base.css").write_text("body{}")
    (site / "js").mkdir()
    (site / "js" / "nav.js").write_text("1")
    (site / "fonts").mkdir()
    (site / "fonts" / "serif.woff2").write_bytes(b"f")
    calls = _fake_aws(monkeypatch, manifest={"index.html": "old"})

    deploy.main(["--output", str(site)])

    uploads = [c for c in calls if c[:2] == ("s3", "cp") and "--recursive" in c]
    headers = {
        c[c.index("--cache-control") + 1] if "--cache-control" in c else None
        for c in uploads
    }
    # One upload per header: pages (none), fonts, and CSS and JS together.
    assert len(uploads) == 3
    assert headers == {
        None,
        "public, max-age=2592000",
        "public, max-age=31536000, immutable",
    }
    assert deploy.cache_control("css/base.css") == "public, max-age=31536000, immutable"
    assert deploy.cache_control("fonts/serif.woff2") == "public, max-age=2592000"
    assert deploy.cache_control("teams/t1.html") is None


def test_full_upload_resends_long_cached_files_with_their_headers(site, monkeypatch):
    (site / "css").mkdir()
    (site / "css" / "base.css").write_text("body{}")
    calls = _fake_aws(monkeypatch, manifest=None)

    deploy.main(["--output", str(site)])

    verbs = [c[:2] for c in calls]
    sync = verbs.index(("s3", "sync"))
    assert any(
        "--cache-control" in c and "immutable" in c[c.index("--cache-control") + 1]
        for c in calls[sync:]
    )
