"""Other-games publishing stays within its prefix and survives partial deploys."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from prometheus.site import config, games
from prometheus.site.render import env

ROOT = Path(__file__).resolve().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


deploy_site = load_script("deploy_site")
deploy_games = load_script("deploy_games")
render_games = load_script("render_games")


def test_render_fixture_without_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setitem(env.globals, "nav", env.globals["nav"])
    source = tmp_path / "feeds"
    source.mkdir()
    (source / "valorant.json").write_bytes(
        (ROOT / "tests/fixtures/game_feed.json").read_bytes()
    )
    feeds = games.load_feeds(source)
    monkeypatch.setattr(games, "load_feeds", lambda: feeds)
    summary = render_games.main()
    assert "3 pages written" in summary
    assert "Other games" in (tmp_path / "other/valorant.html").read_text()
    assert {p.name for p in tmp_path.iterdir()} == {"other", "feeds"}


@pytest.mark.parametrize("old", [None, {}, {"gone.html": "x"}])
def test_deploy_scope_manifest_cache_and_order(tmp_path, monkeypatch, old):
    other = tmp_path / "other"
    other.mkdir()
    (other / "cs2.html").write_text("calls")
    (other / "cs2.json").write_text("{}")
    (tmp_path / "index.html").write_text("league")
    monkeypatch.setenv("DEPLOYMENT_BUCKET", "fake-offline-bucket")
    calls = []

    def aws(*args, **kwargs):
        calls.append(args)
        if kwargs.get("capture"):
            if old is None:
                raise subprocess.CalledProcessError(1, "aws")
            return json.dumps(old)
        return ""

    monkeypatch.setattr(deploy_games, "aws", aws)
    monkeypatch.setattr(deploy_site, "aws", aws)
    deploy_games.main(["--output", str(tmp_path)])
    manifest_url = "s3://fake-offline-bucket/deploy/other-manifest.json"
    assert calls[0][2] == manifest_url
    assert calls[1][:3] == ("s3", "rm", manifest_url)
    assert calls[-1][3] == manifest_url
    uploads = [c for c in calls if "--recursive" in c]
    assert len(uploads) == 1
    assert uploads[0][3] == "s3://fake-offline-bucket/current/other"
    assert uploads[0][-1] == "public, max-age=60"
    for call in calls:
        if call[:2] == ("s3api", "delete-objects"):
            assert json.loads(call[-1])["Objects"] == [
                {"Key": "current/other/gone.html"}
            ]
    new = deploy_games.build_manifest(other)
    assert deploy_games.plan(new, new, always=()) == ([], [])
    assert set(new) == {"cs2.html", "cs2.json"}
    assert any(c[:2] == ("s3", "sync") for c in calls) == (old is None)


def test_manifest_is_not_saved_after_failed_upload(tmp_path, monkeypatch):
    (tmp_path / "other").mkdir()
    (tmp_path / "other/cs2.html").write_text("calls")
    monkeypatch.setenv("DEPLOYMENT_BUCKET", "fake")
    calls = []

    def aws(*args, **kwargs):
        calls.append(args)
        return "{}"

    def fail(*args, **kwargs):
        raise RuntimeError("upload failed")

    monkeypatch.setattr(deploy_games, "aws", aws)
    monkeypatch.setattr(deploy_games, "upload_files", fail)
    with pytest.raises(RuntimeError, match="upload failed"):
        deploy_games.main(["--output", str(tmp_path)])
    assert [c[:2] for c in calls] == [("s3", "cp"), ("s3", "rm")]


def test_workflow_guards_and_restore_order():
    workflow = (ROOT / ".github/workflows/games.yml").read_text()
    assert "workflow_dispatch:" in workflow and 'cron: "27 * * * *"' in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert "group: games\n  cancel-in-progress: false" in workflow
    assert "uv sync --frozen --no-dev" in workflow
    assert "setup_db" not in workflow and "cloudfront" not in workflow.lower()
    assert "if [[ -d output/other ]]" in workflow
    publish = (ROOT / ".github/workflows/publish.yml").read_text()
    restore = publish.index("      - name: Restore game feeds")
    following = publish[restore : publish.index("      - name:", restore + 10)]
    assert "if: env.CAN_USE_AWS == 'true'" in following
    assert "DATA_BACKUP_BUCKET: ${{ vars.DATA_BACKUP_BUCKET }}" in following
    assert restore < publish.index("uv run python scripts/build_site.py")


def test_restore_shell_syntax():
    subprocess.run(["bash", "-n", str(ROOT / "scripts/game_feeds.sh")], check=True)
