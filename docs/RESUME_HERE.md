# Resume Here

Last worked on: **2026-07-31**. Read this first when picking the build back up.

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
| 13 — AWS CDK | ⬜ Not started |
| 14 — AWS App Runner deployment | ⬜ Not started |

## The one blocker that matters: Bedrock token quota

Everything currently blocked traces back to one thing:
```
ThrottlingException: Too many tokens per day, please wait before trying again.
```
on `bedrock-runtime invoke_model` (both Claude and Titan Embeddings — it's an
account-wide budget, not per-model).

**First thing to do when resuming:**
```bash
cd F:/AIML_Apps/PlaybookIQ
uv run python scripts/smoke_test_bedrock.py
```
- If this returns real Claude responses for both Haiku and Sonnet → quota has cleared,
  proceed to the checklist below.
- If still throttled → either wait longer, or go to **AWS Console → Service Quotas →
  Amazon Bedrock** and request an increase on the relevant "tokens per day" quota (note:
  `playbookiq-dev` doesn't have `servicequotas:*` permissions to do this via CLI — would
  need a console user with broader access, or an added IAM grant).

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
   `delete-collection` / `delete-security-policy` / `delete-access-policy`).
7. **Phase 7 (real Bedrock Agent):** create the Agent + `GetPlayerStats` action group,
   backed by either a Lambda or "Return of Control" mode (lower friction — recommended given
   time already spent on IAM back-and-forth this session).
8. **Phase 13 (CDK):** migrate the manually-created S3 bucket + OpenSearch
   Serverless collection into `cdk/playbookiq_stack.py` as code.
9. **Phase 14 (App Runner):** push the image to ECR, deploy via CDK's App Runner
   construct with a scoped instance role (no baked-in credentials).

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

## Cost status as of last session end

Everything continuously-billed was torn down before pausing:
- OpenSearch Serverless collection + all 3 policies: **deleted**
- Docker containers: **stopped**
- No App Runner, CDK stacks, Lambda functions, or EC2 instances exist

Remaining resources (S3 bucket, IAM user, Bedrock Guardrail) are pay-per-use or free at
rest — safe to leave indefinitely.
