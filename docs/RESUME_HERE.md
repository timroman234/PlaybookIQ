# Resume Here

Last worked on: **2026-08-01**. Read this first when picking the build back up.

See [`LEARNING_JOURNAL.md`](./LEARNING_JOURNAL.md) for the full narrative of what happened
and why. This doc is just the practical "what to do next" checklist.

## Current status

| Phase | Status |
|---|---|
| 0 — Scaffolding, git, environment | ✅ Done |
| 1 — AWS IAM + Bedrock model access | ✅ Done (`playbookiq-dev` user + profile, Bedrock access granted) |
| 2 — Synthetic sports data | ✅ Done |
| 3 — Pluggable storage interface (local) | ✅ Done |
| 4 — Real Bedrock model invocation | ⚠️ Code + mocked tests done; **live smoke test blocked by account-wide Bedrock token throttle** |
| 5 — Embeddings + local RAG | ⚠️ Code + tests done; **live ingestion blocked by the same throttle** |
| 6 — Bedrock Guardrails | ✅ Done — created, published, verified live |
| 7 — Bedrock Agents / Action Groups | ⚠️ Local tool contract (`get_player_stats`) done; **real Bedrock Agent not yet created** (deferred due to quota + time) |
| 8 — FastAPI service layer | ✅ Done |
| 9 — Streamlit frontend | ✅ Done, verified live in browser |
| 10 — Containerization | ✅ Done, built + ran + verified live in browser |
| 11 — Real S3 swap-in | ✅ Done — bucket created, data uploaded, verified |
| 12 — Real OpenSearch Serverless + Bedrock KB | ⚠️ Collection + index + policies were created and verified, **then torn down** to stop billing once the Bedrock quota blocked ingestion. Code (`OpenSearchServerlessBackend`) is done and unit-tested. Bedrock Knowledge Base itself was never created. |
| 13 — AWS CDK | ✅ Done — bootstrap → synth → deploy → verify → destroy all done live against real AWS (see below) |
| 14 — AWS App Runner deployment | ⬜ Not started |

## The one blocker that matters: Bedrock token quota

**Update (2026-08-01):** re-checked after a full day — still blocked, same error:
```
ThrottlingException: Too many tokens per day, please wait before trying again.
```
on `bedrock-runtime invoke_model` (both Claude and Titan Embeddings — it's an
account-wide budget, not per-model). **This did not clear on a simple 24h wait**, so it's
not a rolling daily reset — it needs an explicit fix, not more waiting.

We checked **AWS Console → Service Quotas → Amazon Bedrock** to request an increase, but
almost all relevant quotas showed as **"Not Available"/not adjustable** — this is common
for newer Bedrock models (AWS centrally controls this GPU-constrained inference capacity,
there's often no self-service dial at all) and/or reflects this being a very new account
without an established usage/billing history yet.

**Next things to try, in order:**
1. **AWS Support case** — even Basic (free) support can open a "Service limit increase"
   case for Bedrock through the Support Center; this sometimes succeeds where the
   self-service Service Quotas UI shows "Not adjustable."
2. **Let the account age** — usage/billing history sometimes unlocks higher default quotas
   automatically after the account has a completed billing cycle or two.
3. **First thing to check when resuming, regardless of the above:**
   ```bash
   cd F:/AIML_Apps/PlaybookIQ
   uv run python scripts/smoke_test_bedrock.py
   ```
   If this returns real Claude responses for both Haiku and Sonnet, the quota has cleared —
   proceed to the checklist below.

**In the meantime**, Phase 13 (CDK) is now fully done without needing Bedrock at all — see
below. Phase 14 (App Runner) is next and also doesn't strictly need Bedrock to deploy
(though the deployed app's `/query` endpoint won't produce real answers until the quota
clears).

## Checklist once the quota clears

1. **Verify plain Bedrock invocation:**
   `uv run python scripts/smoke_test_bedrock.py`
2. **Verify Guardrails still work:**
   `uv run python scripts/smoke_test_guardrails.py`
3. **Ingest synthetic data into the local vector store:**
   `uv run python scripts/ingest_documents.py`
   then `uv run python scripts/query_smoke_test.py "What is Isaiah Whitfield's injury status?"`
   to confirm local RAG end-to-end (Phase 5 real verification).
4. **Recreate OpenSearch Serverless** (Phase 12 — do this in one focused session, tear down
   promptly afterward):
   ```bash
   aws opensearchserverless create-security-policy --profile playbookiq --region us-east-1 \
     --name playbookiq-encryption --type encryption --policy file://scripts/opensearch/encryption_policy.json
   aws opensearchserverless create-security-policy --profile playbookiq --region us-east-1 \
     --name playbookiq-network --type network --policy file://scripts/opensearch/network_policy.json
   aws opensearchserverless create-access-policy --profile playbookiq --region us-east-1 \
     --name playbookiq-access --type data --policy file://scripts/opensearch/data_access_policy.json
   aws opensearchserverless create-collection --profile playbookiq --region us-east-1 \
     --name playbookiq-vectors --type VECTORSEARCH
   # poll until ACTIVE:
   aws opensearchserverless batch-get-collection --profile playbookiq --region us-east-1 \
     --names playbookiq-vectors --query "collectionDetails[0].status"
   # then get the endpoint:
   aws opensearchserverless batch-get-collection --profile playbookiq --region us-east-1 \
     --names playbookiq-vectors --query "collectionDetails[0].collectionEndpoint" --output text
   ```
   Put the endpoint into `.env` as `OPENSEARCH_COLLECTION_ENDPOINT`, then:
   ```bash
   uv run python scripts/opensearch/create_index.py
   ```
   Set `VECTOR_STORE_BACKEND=opensearch_serverless` in `.env`, then re-run
   `ingest_documents.py` — it now uses the `get_vector_store()` factory, so the `.env` flag
   controls where it writes without any code changes.
5. **Create the Bedrock Knowledge Base** (never yet attempted): point it at the S3 bucket
   (`playbookiq-raw-docs-206152729458`) as the data source and the OpenSearch Serverless
   collection as the vector store, using Titan Embeddings V2. Note this likely needs its
   own service role — either let the Bedrock console's KB creation wizard auto-create one
   (simplest), or grant `playbookiq-dev` scoped `iam:CreateRole`/`PutRolePolicy` if doing it
   via CLI.
6. **Tear down OpenSearch Serverless again** once verified (same delete commands as before —
   see `LEARNING_JOURNAL.md` §7 or just reverse the create commands above with
   `delete-collection` / `delete-security-policy` / `delete-access-policy`) — or, since
   Phase 13's CDK stack now reproduces this exact setup as code, just use
   `cd cdk && cdk destroy` instead of the manual delete commands (see the CDK section
   below).
7. **Phase 7 (real Bedrock Agent):** create the Agent + `GetPlayerStats` action group,
   backed by either a Lambda or "Return of Control" mode (lower friction — recommended given
   time already spent on IAM back-and-forth this session).
8. **Phase 14 (App Runner):** push the image to ECR, extend `cdk/playbookiq_stack.py` with
   an App Runner service + scoped instance role (no baked-in credentials), `cdk deploy`.

## Phase 13 (CDK) — done, here's what exists

`cdk/app.py` + `cdk/playbookiq_stack.py` define the S3 bucket + OpenSearch Serverless
collection (3 policies + collection) as code — verified with a full live
bootstrap → synth → deploy → verify → destroy cycle on 2026-08-01 (~7 minutes of
OpenSearch Serverless exposure, negligible cost). The stack currently creates a
**separate** CDK-managed bucket (`playbookiq-cdk-docs-<account-id>`) rather than importing
the Phase 11 manually-created one (`playbookiq-raw-docs-206152729458`), to avoid a naming
conflict — both exist independently; consolidate later if desired.

To redeploy: `cd cdk && AWS_PROFILE=playbookiq AWS_REGION=us-east-1 cdk deploy --require-approval never`
(bootstrap already done for this account/region, no need to repeat). **Remember to
`cdk destroy` promptly after verifying** — the collection bills the moment it's `ACTIVE`.

Getting CDK working needed two more IAM grants beyond what Phase 1/12 already had:
- `AWSCloudFormationFullAccess` (managed policy) — CDK deploy/destroy is fundamentally
  CloudFormation stack operations.
- IAM role management scoped to `cdk-*`-named roles, plus `ecr:*` and scoped `ssm:*`,
  added to the existing custom `PlaybookIQOpenSearchServerlessAccess` policy — needed for
  `cdk bootstrap` to create its one-time deployment roles
  (`cdk-hnb659fds-*`) and asset repositories. See `LEARNING_JOURNAL.md` for the exact
  policy JSON.

## Things already resolved — don't redo this troubleshooting

- `playbookiq-dev` IAM user exists with `AmazonBedrockFullAccess`, `AmazonS3FullAccess`,
  `AmazonOpenSearchServiceFullAccess`, and the custom `PlaybookIQOpenSearchServerlessAccess`
  policy (covers `aoss:*` + scoped `iam:CreateServiceLinkedRole`).
- Bedrock model access for Anthropic models is unlocked (use-case form already submitted).
- Model IDs in `.env` are already the verified-working ones for this account
  (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`, `us.anthropic.claude-haiku-4-5-20251001-v1:0`)
  — **do not** revert to the PRD's literal `claude-3-5-sonnet-20240620` ID, it's gone from
  the catalog.
- Bedrock Guardrail `qrt0gx10nvwu` (version `1`) exists and is verified working — no need
  to recreate it.
- S3 bucket `playbookiq-raw-docs-206152729458` exists with all 8 synthetic data files
  already uploaded.
- CDK is bootstrapped for account `206152729458` / `us-east-1` (`CDKToolkit` stack) — no
  need to re-run `cdk bootstrap`, just `cdk deploy` / `cdk destroy` going forward.
- `playbookiq-dev` now also has `AWSCloudFormationFullAccess` plus scoped IAM
  role-management (`cdk-*`), `ecr:*`, and scoped `ssm:*` permissions (needed for CDK) —
  don't re-request these if CDK commands fail for an unrelated reason.

## Cost status as of last session end

Everything continuously-billed was torn down before pausing:
- OpenSearch Serverless collection + all 3 policies: **deleted** (both the manually-created
  one from Phase 12 and the CDK-deployed one from Phase 13's verification)
- Docker containers: **stopped**
- The CDK stack (`PlaybookIQStack`) itself: **destroyed** — only the bootstrap's own
  `CDKToolkit` stack remains (S3 assets bucket, ECR repo, IAM roles — negligible/no idle
  cost, fine to leave for future CDK work)
- No App Runner services, Lambda functions, or EC2 instances exist

Remaining resources (2 S3 buckets, IAM user, Bedrock Guardrail, CDK bootstrap resources)
are pay-per-use or free at rest — safe to leave indefinitely.
