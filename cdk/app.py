#!/usr/bin/env python3
"""CDK app entry point (Phase 13).

Run from the cdk/ directory: `cdk synth`, `cdk diff`, `cdk deploy`, `cdk destroy`.
Account/region come from the CDK CLI's environment (set by the active AWS profile),
not hardcoded here.
"""

import os

import aws_cdk as cdk
from playbookiq_stack import PlaybookIQStack

app = cdk.App()

PlaybookIQStack(
    app,
    "PlaybookIQStack",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)

app.synth()
