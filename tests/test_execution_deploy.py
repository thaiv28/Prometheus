"""Release and activation boundaries without AWS calls or credentials."""

import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_execution import settings
from test_execution_runner import Parameter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy.execution import control, deploy, release


def function_response(source=None, digest=None):
    digest = digest or hashlib.sha256(b"old package").digest()
    return {
        "Configuration": {
            "State": "Active",
            "LastUpdateStatus": "Successful",
            "CodeSha256": base64.b64encode(digest).decode(),
        },
        "Tags": {
            "ExecutionSourceSha256": source or release.source_hash(),
            "ExecutionPackageKey": f"prometheus/execution/releases/{digest.hex()}.zip",
        },
    }


def test_configure_requires_off_and_complete_explicit_limits():
    parameter = Parameter({"mode": "off", "activation_at": None})
    limits = {k: v for k, v in settings().items() if k in control.FIELDS}
    result = control.configure(parameter, "/config", limits)
    assert parameter.value == {"mode": "off", "activation_at": None, **limits}
    assert "50" not in str(result)
    control.configure(parameter, "/config", {"starting_bankroll_usd": "60"})
    assert parameter.value["starting_bankroll_usd"] == "60"
    for invalid in ({"mode": "live"}, {"kelly_fraction": "2"}, {"typo": "1"}, []):
        before = copy.deepcopy(parameter.value)
        with pytest.raises(ValueError):
            control.configure(parameter, "/config", invalid)
        assert parameter.value == before
    parameter.value["mode"] = "live"
    with pytest.raises(ValueError, match="off"):
        control.configure(parameter, "/config", limits)
    empty = Parameter({"mode": "off"})
    with pytest.raises((ValueError, KeyError)):
        control.configure(empty, "/config", {"starting_bankroll_usd": "50"})
    assert not empty.writes


def test_settings_workflow_reads_event_without_printing_limits(
    tmp_path, monkeypatch, capsys
):
    parameter = Parameter({"mode": "off", "activation_at": None})
    limits = {k: v for k, v in settings().items() if k in control.FIELDS}
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"inputs": {"settings": json.dumps(limits)}}))
    monkeypatch.setitem(
        sys.modules, "boto3", SimpleNamespace(client=lambda name: parameter)
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["control", "--parameter", "/config", "--settings-event", str(event)],
    )
    control.main()
    output = json.loads(capsys.readouterr().out)
    assert output == {"mode": "off", "updated_fields": sorted(limits)}
    assert parameter.value["starting_bankroll_usd"] == "50"
    assert parameter.value["mode"] == "off"


def test_activation_requires_matching_healthy_deployment_and_limits():
    parameter = Parameter(settings(mode="off"))
    response = function_response()
    functions = SimpleNamespace(get_function=lambda **_: response)
    for change in ("old_source", "drift", "updating"):
        broken = copy.deepcopy(response)
        if change == "old_source":
            broken["Tags"]["ExecutionSourceSha256"] = "unversioned"
        elif change == "drift":
            broken["Tags"]["ExecutionPackageKey"] = "other.zip"
        else:
            broken["Configuration"]["LastUpdateStatus"] = "InProgress"
        with pytest.raises(ValueError):
            control.set_mode(
                parameter,
                "/config",
                "live",
                functions=SimpleNamespace(
                    get_function=lambda result=broken, **_: result
                ),
                function="runner",
            )
    assert not parameter.writes
    control.set_mode(
        parameter, "/config", "live", functions=functions, function="runner"
    )
    assert parameter.value["mode"] == "live"
    assert parameter.value["starting_bankroll_usd"] == "50"
    control.set_mode(parameter, "/config", "off")
    assert parameter.value["mode"] == "off"


def release_harness(tmp_path):
    package = tmp_path / "code.zip"
    package.write_bytes(b"new package")
    response = function_response(source="unversioned")
    params = {
        "ArtifactsBucketName": "private",
        "CodeObjectKey": response["Tags"]["ExecutionPackageKey"],
        "CodeObjectVersion": "old-version",
        "CodeSourceHash": "unversioned",
        "liveSecretArn": "****",
        "demoSecretArn": "****",
    }
    calls = []
    stack = {
        "StackStatus": "UPDATE_COMPLETE",
        "Parameters": [
            {"ParameterKey": k, "ParameterValue": v} for k, v in params.items()
        ],
        "Outputs": [{"OutputKey": "FunctionName", "OutputValue": "runner"}],
    }

    def upload(**kwargs):
        calls.append(("upload", kwargs))
        return {"VersionId": "pinned-version"}

    def update(**kwargs):
        calls.append(("update", kwargs))
        digest = hashlib.sha256(package.read_bytes()).digest()
        response.update(function_response(digest=digest))

    cf = SimpleNamespace(
        describe_stacks=lambda **_: {"Stacks": [stack]},
        update_stack=update,
        get_waiter=lambda name: SimpleNamespace(
            wait=lambda **kw: calls.append((name, kw))
        ),
    )
    return (
        cf,
        SimpleNamespace(put_object=upload),
        SimpleNamespace(get_function=lambda **_: response),
        package,
        calls,
        stack,
        response,
    )


def test_release_preserves_template_secrets_and_pins_version(tmp_path):
    cf, s3, functions, package, calls, _, _ = release_harness(tmp_path)
    result = deploy.deploy(cf, s3, functions, "execution-stack", package)
    assert result["status"] == "deployed"
    upload, update, wait = calls
    assert (
        upload[1]["Key"]
        == f"prometheus/execution/releases/{hashlib.sha256(package.read_bytes()).hexdigest()}.zip"
    )
    assert update[1]["UsePreviousTemplate"] is True
    parameters = {p["ParameterKey"]: p for p in update[1]["Parameters"]}
    assert parameters["CodeObjectVersion"]["ParameterValue"] == "pinned-version"
    for name in ("ArtifactsBucketName", "demoSecretArn", "liveSecretArn"):
        assert parameters[name] == {"ParameterKey": name, "UsePreviousValue": True}
    assert wait[0] == "stack_update_complete"


def test_release_noop_and_drift_fail_before_writes(tmp_path):
    cf, s3, functions, package, calls, stack, response = release_harness(tmp_path)
    source = release.source_hash()
    for p in stack["Parameters"]:
        if p["ParameterKey"] == "CodeSourceHash":
            p["ParameterValue"] = source
    response["Tags"]["ExecutionSourceSha256"] = source
    assert deploy.deploy(cf, s3, functions, "stack", package)["status"] == "unchanged"
    assert not calls
    response["Configuration"]["CodeSha256"] = base64.b64encode(b"x" * 32).decode()
    with pytest.raises(ValueError, match="drift"):
        deploy.deploy(cf, s3, functions, "stack", package)
    assert not calls


def test_release_rejects_unversioned_upload_and_failed_stack(tmp_path):
    cf, _, functions, package, calls, stack, _ = release_harness(tmp_path)
    with pytest.raises(ValueError, match="versioning"):
        deploy.deploy(
            cf, SimpleNamespace(put_object=lambda **_: {}), functions, "stack", package
        )
    assert not calls
    stack["StackStatus"] = "UPDATE_IN_PROGRESS"
    with pytest.raises(ValueError, match="not ready"):
        deploy.deploy(cf, None, functions, "stack", package)
