"""Release code through the existing stack; never touch trading configuration."""

import argparse
import base64
import hashlib
import json
from pathlib import Path

from deploy.execution.release import source_hash, verify_runtime


def deploy(cf, s3, functions, stack_name, package):
    stack = cf.describe_stacks(StackName=stack_name)["Stacks"][0]
    if stack["StackStatus"] not in {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
    }:
        raise ValueError("Execution stack is not ready for an update")
    params = {p["ParameterKey"]: p.get("ParameterValue") for p in stack["Parameters"]}
    if "CodeSourceHash" not in params:
        raise ValueError("Deploy the execution infrastructure update first")
    function = next(
        o["OutputValue"] for o in stack["Outputs"] if o["OutputKey"] == "FunctionName"
    )
    expected = source_hash()
    deployed = functions.get_function(FunctionName=function)["Configuration"]
    current_digest = base64.b64decode(deployed["CodeSha256"]).hex()
    if (
        deployed.get("State") != "Active"
        or deployed.get("LastUpdateStatus") != "Successful"
        or params["CodeObjectKey"]
        != f"prometheus/execution/releases/{current_digest}.zip"
    ):
        raise ValueError(
            "Current Lambda is not healthy or has code drift; review before releasing"
        )
    if params["CodeSourceHash"] == expected:
        verify_runtime(functions, function, expected)
        return {"status": "unchanged", "source_sha256": expected}
    payload = Path(package).read_bytes()
    checksum = hashlib.sha256(payload).digest()
    key = f"prometheus/execution/releases/{checksum.hex()}.zip"
    uploaded = s3.put_object(
        Bucket=params["ArtifactsBucketName"],
        Key=key,
        Body=payload,
        ChecksumSHA256=base64.b64encode(checksum).decode(),
        ContentType="application/zip",
        Metadata={"source-sha256": expected},
    )
    version = uploaded.get("VersionId")
    if not version or version == "null":
        raise ValueError("Release bucket must have versioning enabled")
    changes = {
        "CodeObjectKey": key,
        "CodeObjectVersion": version,
        "CodeSourceHash": expected,
    }
    cf.update_stack(
        StackName=stack_name,
        UsePreviousTemplate=True,
        Capabilities=["CAPABILITY_IAM"],
        Parameters=[
            {"ParameterKey": name, "ParameterValue": changes[name]}
            if name in changes
            else {"ParameterKey": name, "UsePreviousValue": True}
            for name in params
        ],
    )
    cf.get_waiter("stack_update_complete").wait(
        StackName=stack_name, WaiterConfig={"Delay": 5, "MaxAttempts": 120}
    )
    response = verify_runtime(functions, function, expected)
    if response["Configuration"]["CodeSha256"] != base64.b64encode(checksum).decode():
        raise ValueError("Deployed package checksum mismatch")
    return {
        "status": "deployed",
        "source_sha256": expected,
        "package_sha256": checksum.hex(),
    }


def main():
    import boto3

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", default="ThaivPrometheusExecution")
    parser.add_argument("--package", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            deploy(
                boto3.client("cloudformation"),
                boto3.client("s3"),
                boto3.client("lambda"),
                args.stack,
                args.package,
            )
        )
    )


if __name__ == "__main__":
    main()
