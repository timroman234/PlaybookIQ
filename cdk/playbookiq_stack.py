"""PlaybookIQ CDK stack (Phase 13): S3 bucket + OpenSearch Serverless collection as code.

Mirrors what was created manually in Phases 11-12 (see scripts/opensearch/*.json for the
original policy documents this reproduces) — doing it manually first, then as code here,
is deliberate: it makes the abstraction's value legible rather than assumed.

Bedrock Knowledge Base creation is not yet modeled here — CDK's L2 support for it was
still immature at the time of this build; it stays a documented manual/console step (see
docs/RESUME_HERE.md) or would need an AwsCustomResource wrapping the bedrock-agent API
directly, as a stretch extension.
"""

import json

from aws_cdk import (
    Aws,
    CfnOutput,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_opensearchserverless as aoss,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct

COLLECTION_NAME = "playbookiq-vectors"
IAM_PRINCIPAL_NAME = "playbookiq-dev"


class PlaybookIQStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Document bucket (CDK-managed; separate from the Phase 11 manually-created
        # bucket to avoid a naming collision — see docs/RESUME_HERE.md for consolidation).
        doc_bucket = s3.Bucket(
            self,
            "PlaybookDocsBucket",
            bucket_name=f"playbookiq-cdk-docs-{Aws.ACCOUNT_ID}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # 2. OpenSearch Serverless security policies — required before the collection
        # can be created (encryption + network + data access), matching the 3-policy
        # model discovered manually in Phase 12.
        encryption_policy = aoss.CfnSecurityPolicy(
            self,
            "EncryptionPolicy",
            name="playbookiq-encryption",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [{"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]}],
                    "AWSOwnedKey": True,
                }
            ),
        )

        network_policy = aoss.CfnSecurityPolicy(
            self,
            "NetworkPolicy",
            name="playbookiq-network",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {"ResourceType": "collection", "Resource": [f"collection/{COLLECTION_NAME}"]},
                            {"ResourceType": "dashboard", "Resource": [f"collection/{COLLECTION_NAME}"]},
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )

        data_access_policy = aoss.CfnAccessPolicy(
            self,
            "DataAccessPolicy",
            name="playbookiq-access",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{COLLECTION_NAME}"],
                                "Permission": ["aoss:*"],
                            },
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{COLLECTION_NAME}/*"],
                                "Permission": ["aoss:*"],
                            },
                        ],
                        "Principal": [f"arn:aws:iam::{Aws.ACCOUNT_ID}:user/{IAM_PRINCIPAL_NAME}"],
                    }
                ]
            ),
        )

        # 3. OpenSearch Serverless vector collection — depends on all 3 policies existing
        # first (CDK can't infer this dependency automatically since the policies are
        # referenced by name string, not by construct reference).
        vector_collection = aoss.CfnCollection(
            self,
            "VectorCollection",
            name=COLLECTION_NAME,
            type="VECTORSEARCH",
        )
        vector_collection.add_dependency(encryption_policy)
        vector_collection.add_dependency(network_policy)
        vector_collection.add_dependency(data_access_policy)

        CfnOutput(self, "DocBucketName", value=doc_bucket.bucket_name)
        CfnOutput(self, "CollectionEndpoint", value=vector_collection.attr_collection_endpoint)
