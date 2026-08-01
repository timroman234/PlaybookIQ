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
| 14 — Deploy to the cloud (pivoted: App Runner → **Amazon ECS Express Mode**) | ✅ Done — live public HTTPS endpoint verified in a browser, task role IAM auth confirmed working, then torn down (see below) |

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
there's often no self-service dial at all).

**Update (2026-08-01, later same day):** the account had actually been on AWS's
restricted **Free Plan** this whole time (see the CDK/App Runner section below) — we
manually upgraded it, then re-tested. **The quota was still blocked afterward** with the
identical error, confirmed via both a direct CLI `invoke-model` call and a live query
through the deployed ECS service. So the account-tier upgrade did not, by itself, clear
this — it needs one of the options below.

**Next things to try, in order:**
1. **AWS Support case** — even Basic (free) support can open a "Service limit increase"
   case for Bedrock through the Support Center; this sometimes succeeds where the
   self-service Service Quotas UI shows "Not adjustable."
2. **Let the account age further** — usage/billing history sometimes unlocks higher default
   quotas automatically after the account has a completed billing cycle or two (the account
   upgrade alone wasn't sufficient, but it may still be a precondition combined with more
   elapsed time).
3. **First thing to check when resuming, regardless of the above:**
   ```bash
   cd F:/AIML_Apps/PlaybookIQ
   uv run python scripts/smoke_test_bedrock.py
   ```
   If this returns real Claude responses for both Haiku and Sonnet, the quota has cleared —
   proceed to the checklist below.

**Phases 13 and 14 are both now fully done without ever needing Bedrock to succeed** —
CDK (S3 + OpenSearch Serverless as code) and the ECS Express Mode deployment both verified
live. The only thing genuinely still blocked is real Bedrock-backed answers, everywhere
(local, Docker, and the deployed ECS service all hit the identical quota error).

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
8. **Re-verify Phase 14 end-to-end with real answers**: redeploy the ECS Express service
   (commands below), run a query through the live public URL, and confirm it now returns
   a real grounded Claude response instead of the throttling error — this is the one
   remaining "full" verification, everything else about the deployment already works.

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

## Phase 14 — done, pivoted from App Runner to Amazon ECS Express Mode

**Why the pivot:** AWS App Runner is closed to new customers as of 2026-04-30 (existing
services keep running, but you can't create new ones) — the console explicitly recommends
**Amazon ECS Express Mode** as the replacement. Confirmed via AWS's own docs that Express
Mode still requires a pre-built container image (it automates the surrounding
infrastructure — ALB, HTTPS endpoint, security groups, auto-scaling — not the
containerization step), so all of Phase 10's Docker work carried over unchanged.

**What exists right now:**
- ECR repository: `206152729458.dkr.ecr.us-east-1.amazonaws.com/playbookiq` (image pushed,
  tag `latest`)
- ECS cluster: `playbookiq-cluster` (empty, no running services — free to leave)
- CloudWatch log group: `/ecs/playbookiq`
- 3 IAM roles (all still exist, reusable for redeploy):
  - `playbookiq-ecs-execution-role` (trust: `ecs-tasks.amazonaws.com`,
    `AmazonECSTaskExecutionRolePolicy`)
  - `playbookiq-ecs-infrastructure-role` (trust: `ecs.amazonaws.com`,
    `AmazonECSInfrastructureRoleforExpressGatewayServices`)
  - `playbookiq-ecs-task-role` (trust: `ecs-tasks.amazonaws.com`, custom scoped policy —
    `bedrock:InvokeModel`, `bedrock-agent-runtime:Retrieve`/`InvokeAgent`, S3 on our bucket,
    `aoss:APIAccessAll`)
- **The Express service itself was deleted** after verification (see cost note below) —
  everything above is reusable, so redeploying is just re-running the create command.

**To redeploy** (note: on Windows/Git Bash, prefix with `MSYS_NO_PATHCONV=1` or paths like
`/ecs/playbookiq` get mangled into a Windows filesystem path):
```bash
# rebuild + push if the image changed:
docker build -t playbookiq:local .
docker tag playbookiq:local 206152729458.dkr.ecr.us-east-1.amazonaws.com/playbookiq:latest
aws ecr get-login-password --profile playbookiq --region us-east-1 | docker login --username AWS --password-stdin 206152729458.dkr.ecr.us-east-1.amazonaws.com
docker push 206152729458.dkr.ecr.us-east-1.amazonaws.com/playbookiq:latest

MSYS_NO_PATHCONV=1 aws ecs create-express-gateway-service \
  --profile playbookiq --region us-east-1 \
  --cluster playbookiq-cluster --service-name playbookiq-service \
  --execution-role-arn arn:aws:iam::206152729458:role/playbookiq-ecs-execution-role \
  --infrastructure-role-arn arn:aws:iam::206152729458:role/playbookiq-ecs-infrastructure-role \
  --task-role-arn arn:aws:iam::206152729458:role/playbookiq-ecs-task-role \
  --health-check-path /_stcore/health --cpu 512 --memory 1024 \
  --primary-container "image=206152729458.dkr.ecr.us-east-1.amazonaws.com/playbookiq:latest,containerPort=8501,awsLogsConfiguration={logGroup=/ecs/playbookiq,logStreamPrefix=ecs},environment=[{name=AWS_REGION,value=us-east-1},{name=BEDROCK_SONNET_MODEL_ID,value=us.anthropic.claude-sonnet-4-5-20250929-v1:0},{name=BEDROCK_HAIKU_MODEL_ID,value=us.anthropic.claude-haiku-4-5-20251001-v1:0},{name=BEDROCK_EMBEDDING_MODEL_ID,value=amazon.titan-embed-text-v2:0},{name=BEDROCK_GUARDRAIL_ID,value=qrt0gx10nvwu},{name=BEDROCK_GUARDRAIL_VERSION,value=1},{name=STORAGE_BACKEND,value=s3},{name=S3_BUCKET_NAME,value=playbookiq-raw-docs-206152729458},{name=VECTOR_STORE_BACKEND,value=local},{name=API_BASE_URL,value=http://localhost:8000}]"
```
The output includes the live HTTPS endpoint under `activeConfigurations[0].ingressPaths[0].endpoint`.
Poll `aws ecs describe-services --cluster playbookiq-cluster --services playbookiq-service`
until `deployments[0].rolloutState` is `COMPLETED` (~5 minutes).

**To tear down** (bills continuously while it exists — ALB + Fargate task, ~$0.06-0.08/hr):
```bash
aws ecs describe-services --profile playbookiq --region us-east-1 --cluster playbookiq-cluster \
  --services playbookiq-service --query "services[0].serviceArn" --output text
# then:
aws ecs delete-express-gateway-service --profile playbookiq --region us-east-1 \
  --service-arn <arn-from-above> --monitor-resources RESOURCE --monitor-mode TEXT-ONLY
```
This takes several minutes and tears down everything Express Mode created (ALB, listener,
target groups, security groups, auto-scaling policy). A `DependencyViolation` on the
security group partway through is normal — it resolves itself once the ALB's network
interface finishes detaching (~1 minute), no manual intervention needed.

**Verified on 2026-08-01:** live public endpoint reachable, Carbon-themed UI rendered
correctly, "API: Connected" confirmed (Streamlit → FastAPI over `localhost:8000` inside
the Fargate task), and a real query correctly reached Bedrock using the task role's
temporary credentials (no access keys) — it hit the same account-wide token quota as
everywhere else, proving the deployment itself has zero remaining issues.

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
- The IAM role-management resource pattern was widened from just `cdk-*` to also include
  `playbookiq-*` (in the same custom policy), plus `playbookiq-dev` now also has
  `AmazonECS_FullAccess` and `CloudWatchLogsFullAccess` — needed for ECS Express Mode.
  Don't re-request these either.
- The account was upgraded from AWS's restricted **Free Plan** to a standard account on
  2026-08-01 — this is what actually unblocked App Runner's `SubscriptionRequiredException`
  investigation path (moot now since we pivoted away from App Runner) but did **not**
  clear the Bedrock token quota by itself.
- **AWS App Runner cannot be used going forward** — closed to new customers as of
  2026-04-30. Don't attempt Phase 14 there again; ECS Express Mode is the path (see above).
- ECR repo `playbookiq`, ECS cluster `playbookiq-cluster`, log group `/ecs/playbookiq`, and
  all 3 ECS IAM roles already exist and are reusable — redeploying is just the
  `create-express-gateway-service` call, no setup needed.

## Cost status as of last session end

Everything continuously-billed was torn down before pausing:
- OpenSearch Serverless collection + all 3 policies: **deleted** (both the manually-created
  one from Phase 12 and the CDK-deployed one from Phase 13's verification)
- Docker containers: **stopped**
- The CDK stack (`PlaybookIQStack`) itself: **destroyed** — only the bootstrap's own
  `CDKToolkit` stack remains (S3 assets bucket, ECR repo, IAM roles — negligible/no idle
  cost, fine to leave for future CDK work)
- The ECS Express service (`playbookiq-service`) and everything it provisioned (ALB,
  listener, 2 target groups, security groups, auto-scaling policy, CloudWatch alarm):
  **deleted** — confirmed via `describe-services` (status `INACTIVE`) and a direct
  security-group lookup (`InvalidGroup.NotFound`). Total live exposure was ~25 minutes.
- No App Runner services (can't create new ones anyway), Lambda functions, or EC2 instances
  exist

Remaining resources (2 S3 buckets, IAM user, Bedrock Guardrail, CDK bootstrap resources,
ECR repo, ECS cluster, ECS IAM roles, CloudWatch log group) are pay-per-use or free at rest
— safe to leave indefinitely, and make redeploying ECS Express Mode fast next time.
