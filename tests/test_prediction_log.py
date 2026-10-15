"""A competing writer must never erase the first saved alert or publish stale data."""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prediction_log.sh"


@pytest.fixture
def storage(tmp_path):
    (tmp_path / "data").mkdir()
    remote = tmp_path / "remote.json"
    remote.write_text(
        json.dumps(
            {
                "matches": [
                    {"match_id": "m", "alert": {"team": "BNK FEARX", "at": "first"}}
                ]
            }
        )
    )
    (tmp_path / "data/predictions.json").write_text(
        json.dumps({"matches": [{"match_id": "m"}]})
    )
    (tmp_path / "data/.predictions-etag").write_text('"original"')
    aws = tmp_path / "aws"
    aws.write_text("""#!/usr/bin/env python3
import os,sys,json,shutil
from pathlib import Path
args=sys.argv[1:]
root=Path(os.environ['TEST_STORE'])
with (root/'calls.jsonl').open('a') as f:f.write(json.dumps(args)+'\\n')
if args[:2]==['s3api','head-object']:
    if os.environ.get('NO_REMOTE')=='1':
        print('An error occurred (404): Not Found',file=sys.stderr);sys.exit(1)
    print(os.environ.get('REMOTE_ETAG','"original"'))
elif args[:2]==['s3','cp']:
    if args[2].startswith('s3://'):
        shutil.copyfile(root/'remote.json',args[3])
    else:
        shutil.copyfile(args[2],root/'remote.json')
elif args[:2]==['s3api','put-object']:
    if os.environ.get('LATE_RACE')=='1':
        print('An error occurred (PreconditionFailed): 412',file=sys.stderr);sys.exit(1)
    expected='--if-none-match' if os.environ.get('NO_REMOTE')=='1' else '--if-match'
    assert expected in args
    assert args[args.index(expected)+1]==('*' if expected=='--if-none-match' else '"original"')
    shutil.copyfile(args[args.index('--body')+1],root/'remote.json')
else: raise AssertionError(args)
""")
    aws.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "TEST_STORE": str(tmp_path),
        "PREDICTIONS_BACKUP": "s3://test-bucket/log.json",
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
    }

    def run(*args, **overrides):
        return subprocess.run(
            ["bash", str(SCRIPT), "save", *args],
            cwd=tmp_path,
            env={**env, **overrides},
            capture_output=True,
            text=True,
        )

    return tmp_path, run


@pytest.mark.parametrize("hourly", [False, True])
def test_changed_backup_is_never_overwritten_even_when_entry_count_matches(
    storage, hourly
):
    root, run = storage
    before = (root / "remote.json").read_bytes()
    result = run(
        *(["--if-unchanged"] if hourly else []), REMOTE_ETAG='"new-first-alert"'
    )
    assert (result.returncode == 0) == hourly
    assert (root / "remote.json").read_bytes() == before
    assert "put-object" not in (root / "calls.jsonl").read_text()
    if hourly:
        assert (root / "outputs").read_text() == "saved=false\n"


@pytest.mark.parametrize("new", [False, True])
def test_successful_save_uses_s3_atomic_condition_and_reports_persistence(storage, new):
    root, run = storage
    if new:
        (root / "data/.predictions-etag").write_text("")
    else:
        (root / "data/predictions.json").write_bytes(
            (root / "remote.json").read_bytes()
        )
    result = run(NO_REMOTE="1" if new else "0")
    assert result.returncode == 0, result.stderr
    assert (root / "remote.json").read_bytes() == (
        root / "data/predictions.json"
    ).read_bytes()
    assert (root / "outputs").read_text() == "saved=true\n"


@pytest.mark.parametrize("new", [False, True])
def test_writer_racing_after_head_still_cannot_erase_the_saved_alert(storage, new):
    root, run = storage
    before = (root / "remote.json").read_bytes()
    if new:
        (root / "data/.predictions-etag").write_text("")
    result = run(LATE_RACE="1", NO_REMOTE="1" if new else "0")
    assert result.returncode != 0
    assert "PreconditionFailed" in result.stderr
    assert (root / "remote.json").read_bytes() == before
    assert not (root / "outputs").exists()
