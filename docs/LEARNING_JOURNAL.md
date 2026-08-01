# PlaybookIQ — AWS Learning Journal

This is the full record of what we built, in what order, and — most importantly — every
real AWS error hit and how it got resolved. It exists because the actual point of this
project is not the sports-analytics demo; it's learning the AWS skills underneath it for
a job interview. Real errors and their fixes are worth more here than clean happy-path
narration, so they're kept in, not polished away.

Companion docs:
- [`RESUME_HERE.md`](./RESUME_HERE.md) — exact status and next steps to pick back up
- [`../README.md`](../README.md) — project overview and phase checklist
- Plan file: `C:\Users\admin\.claude\plans\i-need-to-build-zesty-spark.md` — the original 15-phase build plan

---

## 1. Architecture decision: pluggable backends

Before touching AWS at all, we built two small interfaces:

- `StorageBackend` (`app/services/storage_service.py`) — `put_object` / `get_object` / `list_objects`
- `VectorStoreBackend` (`app/services/vector_store.py`) — `upsert` / `query`

Each started with a local implementation (`LocalFileStorage`, `LocalVectorStore`) and later
got a real-AWS implementation (`S3Storage`, `OpenSearchServerlessBackend`) satisfying the
exact same interface. Swapping backends was a one-line `.env` change
(`STORAGE_BACKEND=s3`, `VECTOR_STORE_BACKEND=opensearch_serverless`) — zero changes to
calling code.

**Why this matters for interviews:** "build against an abstraction, swap the
implementation" is itself a cloud-architecture skill independent of any one AWS service.
It's also what made the AWS learning safe and cheap — we could prove the RAG *logic* against
a free local backend before spending anything on the real managed service.

---

## 2. IAM — the recurring theme

### What we did
- Discovered the AWS CLI already had a `default` profile pointing at an IAM user
  (`hearthealthml-dvc`) from a *different* project, with very limited permissions
  (couldn't even run `iam:GetUser` on itself).
- Decided to create a dedicated IAM user, `playbookiq-dev`, scoped to this project, with
  its own named CLI profile (`playbookiq`) — keeping permissions isolated per project
  rather than reusing/widening an existing identity.
- The account owner had to create this user manually in the console (the existing
  credentials didn't have `iam:CreateUser` either) and generate an access key for it.

### A real console UX change worth knowing
When creating the access key, the console no longer just lets you click through — it now
shows:
> "Alternatives recommended: Use AWS CLI v2 + `aws login`/SSO, or use CloudShell"

This reflects AWS's current push away from long-lived static access keys toward
temporary/federated credentials (IAM Identity Center SSO). **For a personal login this is
the right call.** But for a purpose-built automation identity like `playbookiq-dev` — used
by local scripts across many sessions — a rotatable long-lived key is still the correct,
standard pattern (SSO session tokens expire hourly, which is painful for this workflow).
There's a small "I understand the recommendation, proceed anyway" link below the
alternatives to continue creating the key.

### The pattern that repeated all day: AccessDeniedException tells you exactly what to add
Every time we touched a new AWS capability, we hit `AccessDeniedException`, and **the error
message always named the exact IAM action needed**:

| Action attempted | Error named | Fix |
|---|---|---|
| `aws bedrock list-foundation-models` | `bedrock:ListFoundationModels` | Attach `AmazonBedrockFullAccess` |
| `aws opensearchserverless create-security-policy` | `aoss:CreateSecurityPolicy` | Custom policy granting `aoss:*` (no AWS managed policy exists for this — `AmazonOpenSearchServiceFullAccess` covers classic OpenSearch's `es:*` only, **not** Serverless's separate `aoss:*` namespace) |
| `aws opensearchserverless create-collection` | `iam:CreateServiceLinkedRole` on `.../AWSServiceRoleForAmazonOpenSearchServerless` | One-time grant, scoped via a `Condition` on `iam:AWSServiceName` |

**Interview talking point:** least-privilege IAM isn't something you get right upfront by
guessing — the practical workflow is: attempt the action, read the exact action name from
the `AccessDeniedException`, grant precisely that. This is faster and more accurate than
trying to pre-enumerate every permission a workload needs.

### Final permission set for `playbookiq-dev`
- `AmazonBedrockFullAccess`
- `AmazonS3FullAccess`
- `AmazonOpenSearchServiceFullAccess`
- Custom `PlaybookIQOpenSearchServerlessAccess`:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {"Effect": "Allow", "Action": "aoss:*", "Resource": "*"},
      {
        "Effect": "Allow",
        "Action": "iam:CreateServiceLinkedRole",
        "Resource": "arn:aws:iam::*:role/aws-service-role/observability.aoss.amazonaws.com/AWSServiceRoleForAmazonOpenSearchServerless",
        "Condition": {"StringEquals": {"iam:AWSServiceName": "observability.aoss.amazonaws.com"}}
      }
    ]
  }
  ```
  (Intentionally broad for dev speed — a real production rollout would scope `aoss:*` down
  to specific actions and the specific collection ARN, per the plan's IAM-hardening note.)

---

## 3. Amazon Bedrock — model invocation

### The "Model access" page is retired
The PRD (and most tutorials) describe requesting Bedrock model access via a console
"Model access" page with per-model toggles. **That page is gone.** The current flow:
foundation models auto-enable account-wide the first time anyone invokes them — except
Anthropic models specifically require a one-time "use case details" form (a short
questionnaire about intended use) before the first successful invocation. Submitting it
took effect within about a minute in our case (AWS says "up to 15 minutes").

### The PRD's literal model ID is gone
`anthropic.claude-3-5-sonnet-20240620-v1:0` no longer appears in
`aws bedrock list-foundation-models`. **Always re-check the live catalog** rather than
hardcoding a model ID from documentation — catalogs move fast. We resolved current IDs via:
```bash
aws bedrock list-foundation-models --region us-east-1 \
  --query "modelSummaries[?contains(modelId,'claude') || contains(modelId,'titan-embed')].modelId"
```

### Newer models require an inference profile, not a bare model ID
Calling `invoke-model` directly with a newer model ID:
```
ValidationException: Invocation of model ID anthropic.claude-haiku-4-5-... with
on-demand throughput isn't supported. Retry your request with the ID or ARN of an
inference profile that contains this model.
```
Fix: look up the inference profile ID (regional `us.*` or `global.*` prefix) and pass
*that* as the model ID instead:
```bash
aws bedrock list-inference-profiles --region us-east-1 \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId,'claude')].{id:inferenceProfileId,name:inferenceProfileName}"
```
We standardized on `us.*` profiles to stay consistent with pinning everything to
`us-east-1`.

### Even some inference-profile IDs are separately gated
`us.anthropic.claude-sonnet-5` returned `AccessDeniedException` even after the general
Anthropic use-case form was accepted (which had already unblocked
`claude-haiku-4-5`/`claude-sonnet-4-5`). **Lesson:** the very newest model tier in a
provider's lineup can have its own separate access gate beyond the general unlock — don't
assume "Anthropic access granted" means *every* Anthropic model is available. We fell back
to `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, which worked (once past the token
quota — see next section).

### New-account daily token quota
Once past the access-gating issues, real invocation still failed:
```
ThrottlingException: Too many tokens per day, please wait before trying again.
```
This is a new-account default quota, separate from (and stricter than) request-rate
throttling. We confirmed it wasn't a bug in our code by noticing that a **guardrail-blocked
request still succeeded** (see §5) — guardrail interception happens before/without full
generation, so it barely touches the token budget, while a real completion request needs
more than the account currently has.

We also saw a second, different throttle message on the Embeddings model:
```
ThrottlingException: Too many requests, please wait before trying again.
```
This is a request-rate throttle (shorter-lived, clears in seconds-to-minutes) — **different
from the daily-token quota** (which doesn't resolve with a short retry). Telling these two
apart by their exact message text is the difference between "retry in 10 seconds" and
"this needs a Service Quota increase request or a day to pass."

**Remediation options** (for whenever this build resumes):
1. Wait — likely resets on a rolling ~24h window.
2. AWS Console → **Service Quotas → Amazon Bedrock** → search for the relevant
   "on-demand model inference tokens per day/minute" quota → request an increase.
   (Note: `playbookiq-dev` doesn't have `servicequotas:*` permissions to check/request this
   itself — would need an added grant or console access with broader permissions.)

### `bedrock_service.py` design
- Routes between a "Sonnet" (deep synthesis) and "Haiku" (fast/cheap) model ID based on a
  `use_fast_model` flag — the PRD's "cost/latency model routing" pattern.
- Catches `ClientError` with `Code == "AccessDeniedException"` and re-raises as a custom
  `BedrockModelAccessError` with a friendlier message pointing at what to check.
- Accepts optional `guardrail_id`/`guardrail_version` kwargs, passed through as
  `guardrailIdentifier`/`guardrailVersion` on `invoke_model`.
- All of this is unit-tested with a mocked boto3 client (`unittest.mock.patch` on the
  module-level `boto3` import) — no real AWS calls in the test suite, so CI-style runs
  don't cost money or need credentials.

---

## 4. Amazon Titan Embeddings V2

Same `bedrock-runtime invoke_model` API as Claude, just a different model ID
(`amazon.titan-embed-text-v2:0`) and payload shape (`{"inputText": ...}` in,
`response["embedding"]` out — a flat 1024-float list). Subject to the *same* daily token
quota as Claude invocation (confirmed by hitting the identical throttle class), meaning the
account-wide quota isn't per-model — it's a shared budget across all Bedrock invocations.

---

## 5. Amazon Bedrock Guardrails

Created via the **control plane** (`bedrock` client, not `bedrock-runtime`), which is
important: guardrail *creation* is unaffected by the invoke-time token quota above.

```bash
aws bedrock create-guardrail --cli-input-json file://scripts/bedrock_guardrail_config.json
aws bedrock create-guardrail-version --guardrail-identifier <id> --description "Initial published version"
```

Guardrails need a **published, numbered version** (not just `DRAFT`) to be usable via
`guardrailIdentifier`/`guardrailVersion` on `invoke_model` — `create-guardrail-version` does
that promotion.

Our config includes:
- Content filters (hate/insults/sexual/violence/misconduct)
- PII entity redaction (NAME → anonymize, SSN → block, EMAIL/PHONE/AGE → anonymize)
- A denied topic ("MedicalOrLegalAdvice") — Guardrails' topic policy lets you describe a
  category in natural language plus a couple of examples, rather than writing rules
  yourself
- Contextual grounding/relevance checks (anti-hallucination)

**The single most useful discovery of the whole session:** we ran a real end-to-end
verification — sent a PII-laden prompt through `bedrock_service.invoke(...,
guardrail_id=...)` — and it returned our exact `blockedInputMessaging` text ("This request
cannot be processed due to content policy restrictions"), **while plain (non-guardrailed)
calls at the same moment were still hitting the daily token throttle.** This proves two
things simultaneously: the guardrail is correctly wired into the call path (not just
created and ignored), and guardrail-side blocking happens cheaply enough to test even under
a near-exhausted token budget — a genuinely useful operational fact, not just a test-passing
coincidence.

---

## 6. Amazon S3

The most conventional part of the build — no real surprises, which is itself worth noting
(S3's API has been stable for 15+ years; it's the newer/serverless services that have rough
edges).

```bash
aws s3 mb s3://playbookiq-raw-docs-206152729458   # account-ID suffix for global uniqueness
```

`S3Storage` implements `StorageBackend` with `boto3.client("s3")`:
`put_object`/`get_object` map directly; `list_objects` uses the `list_objects_v2`
paginator (correct even though our object count never came close to needing pagination —
matches how you'd actually write this against a bucket of unknown size). `NoSuchKey`
translates to `FileNotFoundError`, matching `LocalFileStorage`'s error contract exactly.

Verified live: uploaded all 8 synthetic data files, confirmed via
`aws s3 ls --recursive`, flipped `STORAGE_BACKEND=s3` in `.env` — zero application code
changes needed.

---

## 7. Amazon OpenSearch Serverless (the centerpiece, and the most expensive lesson)

### Distinct security model
Unlike classic OpenSearch (IAM + optional fine-grained access control), Serverless
requires **three separate policy documents** before a collection can even be created:

1. **Encryption policy** — which KMS key protects the collection (`AWSOwnedKey: true` for
   the simple case)
2. **Network policy** — public vs. VPC access, per resource type (`collection`,
   `dashboard`)
3. **Data access policy** — which IAM principals can do what, at the collection *and*
   index level, via `aoss:*` permission grants — this is genuinely a second, parallel
   permission system layered on top of regular IAM, not a replacement for it

All three had to be created via `aws opensearchserverless create-security-policy` /
`create-access-policy` before `create-collection` would succeed at all.

### `aoss:*` needs its own IAM grant (see §2) — and so does the service-linked role
Both gotchas are documented in the IAM section above, but worth repeating here in context:
this was the single most IAM-permission-hungry AWS service in the whole build.

### Provisioning is asynchronous
`create-collection` returns immediately with `status: CREATING`. We polled with:
```bash
aws opensearchserverless batch-get-collection --names playbookiq-vectors \
  --query "collectionDetails[0].status"
```
until it reported `ACTIVE` (took a few minutes) before the collection endpoint was usable.

### Auth is AWS SigV4, not username/password
Once active, talking to the collection's data plane (creating the k-NN index, indexing
documents, querying) goes through `opensearch-py`'s `AWSV4SignerAuth`, signing HTTPS
requests with the same boto3 credential chain as everything else — there's no separate
OpenSearch-specific login. This is a nice consistency win once you know it, but surprising
if you're coming from self-hosted OpenSearch/Elasticsearch, which usually has its own
username/password or API-key auth layer.

### Index schema
Matches the PRD's mapping exactly:
```json
{
  "settings": {"index.knn": true},
  "mappings": {
    "properties": {
      "vector_field": {"type": "knn_vector", "dimension": 1024,
                        "method": {"name": "hnsw", "engine": "nmslib", "space_type": "cosinesimil"}},
      "text": {"type": "text"},
      "document_type": {"type": "keyword"},
      "player_id": {"type": "keyword"},
      "timestamp": {"type": "date"}
    }
  }
}
```
This is deliberately identical to `LocalVectorStore`'s metadata shape (§1), so
`OpenSearchServerlessBackend` is a pure backend swap for `RagService`, not a redesign.

### Cost model — the big one
OpenSearch Serverless bills **per OCU-hour, continuously, with a ~2 OCU minimum**
(≈$0.24/OCU-hr × 2 ≈ **$0.48/hr, roughly $11-12/day**) — starting the moment the collection
reaches `ACTIVE`, regardless of whether you're actively querying it. This is fundamentally
different from every other service in this build:

| Service | Billing model |
|---|---|
| Bedrock (invoke/embed) | Pay per token, only when called |
| Bedrock Guardrails | Pay per unit processed, only when called |
| S3 | Pay for storage + requests, both negligible at this scale |
| **OpenSearch Serverless** | **Pay per OCU-hour, continuously, whether used or not** |
| (later) App Runner | Pay for compute while the service is running, not scale-to-zero |

**Interview talking point:** distinguishing "pay-per-call managed API" services from
"provisioned, bills-while-it-exists" infrastructure is a core AWS cost-management skill.
The practical habit this taught us: create → verify → tear down, don't leave the
continuously-billed tier running between work sessions.

### What we actually verified before tearing down
- ✅ All 3 security/access policies created
- ✅ Collection created and reached `ACTIVE`
- ✅ k-NN index created with the correct schema
- ✅ `OpenSearchServerlessBackend` code written and unit-tested (mocked)
- ❌ Live document ingestion / retrieval — blocked by the Bedrock token quota (§3), since
  embedding the documents requires a working Titan Embeddings call
- We deleted the collection and all 3 policies once it became clear the quota wasn't going
  to clear quickly in this session, to stop the ~$0.48/hr charge. See `RESUME_HERE.md` for
  exactly how to recreate everything.

---

## 8. Bedrock quota, day 2: it's not a rolling reset

Came back the next day expecting the "tokens per day" throttle (§3) to have cleared.
It hadn't — identical error, verbatim. That ruled out the simplest hypothesis (a rolling
24h window) and meant this needed an actual fix, not more waiting.

Went to **AWS Console → Service Quotas → Amazon Bedrock** to request an increase. Nearly
every relevant quota showed as **"Not Available"** — no self-service increase button at
all. This surprised us enough to wonder if it was something account-specific (a
non-US-issued card on file was the first guess) — **it wasn't**. AWS bills internationally
routinely; card-issuing country doesn't gate Service Quotas. The real explanations, in
likely order:

1. **Many Bedrock inference quotas simply aren't adjustable via self-service at all** —
   AWS centrally manages this because it's GPU-constrained inference capacity, not just a
   policy dial they can turn up on request the way, say, an S3 request-rate limit might be.
2. **Account maturity** — a brand-new account (this one was created same-day) often sits on
   conservative defaults until it has an established usage/billing history.

**The lesson, independent of whether we ever get it raised:** not every AWS quota is
self-service, and "the console won't let me increase it" isn't a dead end — the next lever
is an **AWS Support case** (even Basic/free support can open a service-limit-increase
request for Bedrock), which sometimes succeeds where the Service Quotas UI shows nothing
adjustable. We didn't need to fully resolve this to keep making progress, though — Phase 13
(CDK) doesn't touch Bedrock at all, so we moved there instead of blocking on it.

---

## 9. AWS CDK — infrastructure as code

### The IAM escalation ladder, one more rung
Every new AWS capability in this build has meant one more IAM grant (§2), and CDK was the
biggest jump yet. `cdk bootstrap` — the one-time, per-account/region setup that creates the
`CDKToolkit` CloudFormation stack plus deployment roles, an S3 assets bucket, and an ECR
asset repo — needs:
- `cloudformation:*` (attached the managed `AWSCloudFormationFullAccess` policy) — CDK
  deploy/destroy is fundamentally CloudFormation stack management under the hood.
- `iam:CreateRole`/`AttachRolePolicy`/`PutRolePolicy`/etc., because bootstrap provisions
  its own deployment roles (`cdk-hnb659fds-cfn-exec-role-...`,
  `cdk-hnb659fds-deploy-role-...`, `cdk-hnb659fds-file-publishing-role-...`, etc.) —
  scoped this to `arn:aws:iam::*:role/cdk-*` rather than granting blanket IAM admin.
- `ecr:*` (for the container asset repository) and scoped `ssm:*` (for the
  `/cdk-bootstrap/hnb659fds/version` parameter CDK uses to track bootstrap versions).

**Interview talking point:** CDK's bootstrap step is doing real, visible work — it's not
magic. Running it with `--verbose` or just watching the CloudFormation events (as we did)
shows exactly what it creates: `LookupRole`, `FilePublishingRole`, `ImagePublishingRole`,
`CloudFormationExecutionRole`, `DeploymentActionRole`, a staging S3 bucket, an ECR repo, and
an SSM parameter. Understanding *why* CDK needs each of these (cross-account/cross-region
lookups, asset publishing, the actual deploy execution role CloudFormation assumes) is a
better answer in an interview than "you just run `cdk bootstrap` once."

### L1 constructs for a service without full L2 support
OpenSearch Serverless doesn't have rich L2 (object-oriented, sensible-defaults) CDK
constructs yet — we used the `Cfn*` L1 constructs (`CfnCollection`, `CfnSecurityPolicy`,
`CfnAccessPolicy`), which map almost 1:1 onto raw CloudFormation resource properties. This
meant hand-building the same policy JSON documents we'd already used manually via the CLI
(§7) and passing them as JSON strings into `policy=json.dumps(...)` properties — more
verbose than a typical L2 experience (no smart defaults, no convenience methods), but a
direct, honest mapping onto what the console/CLI does. `CfnCollection` won't create
successfully unless its 3 policies already exist, and **CDK doesn't infer this dependency
automatically** since the policies are referenced by name string, not by construct
reference — we had to add explicit `.add_dependency(...)` calls, or `cdk deploy` will
happily try to create the collection before its policies exist and fail exactly like the
manual CLI attempt did in §7.

### The full lifecycle, verified live
```bash
cdk bootstrap aws://206152729458/us-east-1   # one-time per account/region
cdk synth                                     # validates the template, zero AWS calls
cdk deploy --require-approval never            # creates real resources
cdk destroy --force                            # tears them down
```
Ran the complete cycle in one focused session: `cdk synth` produced valid CloudFormation,
`cdk deploy` created both the S3 bucket and a fully `ACTIVE` OpenSearch Serverless
collection (~5 minutes, mostly waiting on the collection), we verified both existed via
plain `aws` CLI calls (not just trusting CDK's own "success" message), then `cdk destroy`
removed everything cleanly in about 11 seconds. Total OpenSearch Serverless billing
exposure: roughly 7 minutes (~$0.05) — proof that "create, verify, tear down" as a
deliberate habit (§7) works in practice, not just as a principle.

### Doing it manually first, then as code, was the right call
Having already built the OpenSearch Serverless setup by hand via the CLI (§7) made the CDK
version easy to sanity-check — every property in `CfnSecurityPolicy`/`CfnAccessPolicy`
mapped directly onto JSON we'd already written and understood. Writing the CDK stack
*first*, without that manual context, would have meant debugging CDK abstractions and
OpenSearch Serverless's unusual security model at the same time — worth remembering as a
general learning strategy: do the manual/CLI version of something once before automating
it, so you can tell "CDK is wrong" apart from "I don't understand this AWS service yet."

---

## 10. Docker — a lesson in resource constraints, not AWS

Not an AWS topic, but worth recording because it consumed real troubleshooting time and is
a genuinely common environment issue: this machine has only **8GB total RAM**, and at one
point had as little as **~275MB free** while Docker Desktop's WSL2 backend was starting.
Symptoms were confusing at first — background shell commands were silently killed with zero
output, `docker info` hung instead of erroring quickly. The actual fix was simply freeing
memory (closing other applications) so the WSL2 VM had room to finish initializing; once
free memory rose to ~1.3GB, `docker info` returned a full `Server:` section immediately.

**Lesson for any resource-constrained dev environment:** a hanging command with zero output
is a different failure mode than an error message, and often means memory/CPU starvation
rather than a logic bug — check `wmic OS get FreePhysicalMemory` (or Task Manager) before
assuming the tool itself is broken.

Once memory freed up: `docker build` succeeded with the `uv`-based Dockerfile, and
`docker run` produced a container serving both FastAPI (backgrounded) and Streamlit
(foreground) on the ports we expected — verified in a real browser, not just `curl`.

---

## 11. FastAPI + Streamlit — the app layer

Two real processes, not a monolith: Streamlit (`app/ui.py`) is a pure HTTP client of
FastAPI (`app/main.py`) via `requests`, matching the PRD's architecture diagram
("Streamlit Frontend → REST/Boto3 API → FastAPI Service Container") rather than importing
service modules directly in-process. This is the more realistic pattern for how AWS-hosted
backends are actually composed — one service calling another over the network — and it's
what let us containerize both into a single App Runner-ready image (§8) with Streamlit
calling `http://localhost:8000` inside the same container.

FastAPI's `Depends(...)` dependency-injection pattern made every endpoint trivially
testable via `app.dependency_overrides[get_bedrock_service] = lambda: mock_bedrock` — no
real AWS credentials or network calls needed in `tests/test_main.py`.

---

## 12. AWS account tiers: the "Free Plan" and why so much felt stuck

A full day into hitting friction — the Bedrock daily token quota showing "Not Available"
for a Service Quota increase, `AWSAppRunnerFullAccess` not fixing App Runner's
`SubscriptionRequiredException` — the actual root cause surfaced: this account had been on
AWS's newer **Free Plan** signup path the entire time, not a standard account. The Free
Plan intentionally restricts access to a curated set of free-tier-eligible services until
you upgrade, even with a valid payment method and active free credits on file.

**This retroactively explains a lot of the day's friction** that looked like isolated IAM
or quota problems but was actually one root cause wearing different masks. After manually
upgrading the account (Billing and Cost Management → look for an "Upgrade your account"
prompt), the App Runner `SubscriptionRequiredException` was still present for an unrelated
reason (see §13), and the Bedrock daily-token quota *also* didn't clear immediately —
account-tier upgrades don't necessarily propagate to every downstream quota/service gate
instantly. **Lesson:** when several apparently-unrelated services all fail in oddly similar
"you're not allowed to use this" ways on the same brand-new account, check the account
tier/plan itself before assuming each is an independent IAM or quota problem to debug one
at a time.

---

## 13. AWS App Runner: closed to new customers mid-project

Went to deploy Phase 14 and hit a wall that had nothing to do with permissions or quotas:
the App Runner console displayed —

> "Starting April 30, 2026, AWS App Runner is no longer accepting new customers... For
> deploying and running containerized applications, we recommend Amazon ECS Express Mode."

This is a genuinely different category of blocker than everything else in this build: not
a missing permission, not a quota, but a **service AWS itself is winding down**. No IAM
grant or account upgrade fixes this — a *new* App Runner service simply cannot be created
on this account anymore, full stop (existing App Runner services elsewhere remain
operational, per the notice).

**Lesson for the interview:** part of staying current in a fast-moving cloud platform is
knowing when to stop debugging and start reading the actual guidance the platform is
handing you. AWS explicitly named its own recommended replacement (ECS Express Mode) right
in the deprecation notice — the correct move was to pivot immediately rather than fight to
resurrect a sunsetting service. This is also a legitimately good interview story: it shows
adapting to platform changes in real time rather than working from stale documentation.

**Before pivoting, we verified a specific assumption rather than guessing:** would ECS
Express Mode remove the need for the Dockerfile/containerization work already done in
Phase 10? Checked AWS's own docs and announcement post rather than assume — answer: no.
Express Mode automates the *infrastructure* around a container (load balancer, HTTPS
endpoint, security groups, auto-scaling) but still requires you to bring a pre-built
container image; it does not build images from source. So all of Phase 10's work carried
over unchanged — only the deployment *target* changed.

---

## 14. Amazon ECS Express Mode — the actual Phase 14 deployment

### Two more IAM roles, plus a permission-scope adjustment
ECS Express Mode needs exactly two roles (a third, the task role, is really "your app's
own permissions" and technically optional but essential for anything beyond a static demo):

1. **Task execution role** (trust: `ecs-tasks.amazonaws.com`) — lets the ECS agent pull the
   image from ECR and write logs. Managed policy: `AmazonECSTaskExecutionRolePolicy`.
2. **Infrastructure role** (trust: `ecs.amazonaws.com`) — lets ECS provision the ALB, target
   groups, security groups, and auto-scaling on your behalf. Managed policy:
   `AmazonECSInfrastructureRoleforExpressGatewayServices`.
3. **Task role** (trust: `ecs-tasks.amazonaws.com`, same as execution role's trust, different
   purpose) — what the *application code* actually assumes at runtime. We scoped this to
   exactly what PlaybookIQ needs: `bedrock:InvokeModel`, `bedrock-agent-runtime:Retrieve`/
   `InvokeAgent`, `s3:GetObject`/`PutObject`/`ListBucket` scoped to our bucket ARN, and
   `aoss:APIAccessAll` scoped to the collection ARN pattern (even though no collection
   existed at the time — IAM policies can reference resources that don't exist yet).

Creating these under our own naming convention (`playbookiq-ecs-*`) required widening the
IAM role-management permission we'd scoped to `cdk-*` role names for Phase 13 — extended
the `Resource` list to also cover `arn:aws:iam::*:role/playbookiq-*`, keeping it scoped
rather than opening role creation to `*`.

Separately, `playbookiq-dev` also needed two more managed policies neither Phase 1 nor
Phase 13 had granted: `AmazonECS_FullAccess` and `CloudWatchLogsFullAccess` (ECS Express
Mode logs to CloudWatch, and the execution role's managed policy only covers
`logs:CreateLogStream`/`PutLogEvents`, not `logs:CreateLogGroup` — the log group itself has
to be created ahead of time by a principal that *does* have that permission).

### The actual command
```bash
aws ecs create-express-gateway-service \
  --cluster playbookiq-cluster \
  --service-name playbookiq-service \
  --execution-role-arn arn:aws:iam::206152729458:role/playbookiq-ecs-execution-role \
  --infrastructure-role-arn arn:aws:iam::206152729458:role/playbookiq-ecs-infrastructure-role \
  --task-role-arn arn:aws:iam::206152729458:role/playbookiq-ecs-task-role \
  --health-check-path /_stcore/health \
  --cpu 512 --memory 1024 \
  --primary-container image=<ecr-uri>:latest,containerPort=8501,awsLogsConfiguration={logGroup=/ecs/playbookiq,logStreamPrefix=ecs},environment=[...]
```

Two details worth remembering:
- **Health check path**: our single container only exposes Streamlit externally
  (port 8501) — FastAPI's own `/health` endpoint (Phase 8) is internal-only, reachable at
  `localhost:8000` *inside* the container, not from the ALB. Streamlit ships its own
  built-in health endpoint, **`/_stcore/health`**, which is what the ALB actually needs to
  hit — using our FastAPI `/health` path here would have pointed the health check at a port
  nothing outside the container can reach.
- **Environment variables, not baked into the image**: model IDs, guardrail ID, bucket
  name, storage/vector-store backend flags — all passed via `--primary-container`'s
  `environment` list. No AWS credentials of any kind are in there; the task role provides
  those automatically via the container credential provider chain, identical in spirit to
  how the app already worked locally against a named CLI profile — just swapping "profile"
  for "task role" as the credential source.

### Verified live, and it actually proved something
The service came up with an auto-generated HTTPS endpoint
(`https://pl-*.ecs.us-east-1.on.aws`) within about 5 minutes. Opened it in a real browser —
full Carbon-themed UI, sidebar showing "API: Connected" (confirming Streamlit correctly
reaches FastAPI over `localhost:8000` *inside the Fargate task*, not just inside Docker
Desktop locally). Ran a real query through the public URL, got a 500 — checked the
CloudWatch logs (`aws logs tail /ecs/playbookiq`) and found the exact same
`ThrottlingException: Too many tokens per day` we'd been tracking all along, but this time
raised from **inside the deployed container, using the task role's temporary credentials**
— no access keys anywhere. That's a genuinely meaningful verification: the task role's IAM
permissions and the container credential chain both work correctly; the only remaining
blocker is the account-wide Bedrock quota, identical to every environment we've tested in
(local, Docker Desktop, now Fargate).

### Teardown: not everything is a `delete-service` call
Deleting an Express service isn't a single quick API call the way `docker stop` is —
`aws ecs delete-express-gateway-service --service-arn <arn>` triggers ECS to tear down
*every* managed resource it created (ALB, listener, listener rule, 2 target groups,
security groups, auto-scaling policy, scalable target, CloudWatch rollback alarm) in
dependency order. Watching it with `--monitor-resources RESOURCE --monitor-mode TEXT-ONLY`
showed a real, instructive failure-and-retry: the load balancer's security group hit a
`DependencyViolation` ("has a dependent object") for about a minute after the ALB itself
was deleted — the ALB's network interface takes a short time to fully detach before AWS
will let you delete the security group it was attached to. ECS's own deletion process
retried automatically until it succeeded ("Service is inactive"), rather than failing
outright. **Lesson:** `DependencyViolation` on a security group deletion, right after
deleting whatever was using it, is usually a race condition to wait out, not a sign
something is stuck — verify by re-checking after a minute before assuming a manual
intervention is needed.

Total cost exposure for the live verification: roughly 25 minutes of Fargate task + ALB
time (created ~16:44 UTC, fully torn down ~17:12 UTC) — on the order of a few cents,
consistent with our "create, verify, tear down" discipline from OpenSearch Serverless (§7)
and CDK (§9).

---

## 15. Bedrock Agents Classic: closed to new customers too — pivoting Phase 7 before building it

The PRD's Phase 7 design ("Bedrock Agents / MCP," a `GetPlayerStats` action group) targets
what AWS now calls **Bedrock Agents Classic**. Before attempting to build it, we checked
AWS's current docs — good thing, because the exact same App Runner-shaped problem (§13)
was waiting:

> "Amazon Bedrock Agents (now Amazon Bedrock Agents Classic) is no longer open to new
> customers. For capabilities similar to Bedrock Agents Classic, explore Amazon Bedrock
> AgentCore. Existing customers can continue to use the service as normal."

**This time we caught it before writing any code or hitting a live error**, purely by
asking "would this even work on a new account" before starting — a direct application of
§13's lesson (read the platform's own current guidance rather than build from
documentation/PRD text that may have gone stale).

### What replaces it: Amazon Bedrock AgentCore
AgentCore is a meaningfully different shape of service than Classic Agents, not just a
renamed version of it:

| | Bedrock Agents Classic | Bedrock AgentCore |
|---|---|---|
| Model | AWS-owned orchestration; configure, don't code | Framework-agnostic infrastructure you compose |
| Tool mechanism | "Action groups" backed by Lambda | Gateway (exposes APIs/Lambda as tools), MCP servers, Browser, Code Interpreter |
| Shape | One bundled service | Modular primitives: Runtime, Memory, Gateway, Identity, Observability, Policy, Evaluations |
| Works with | Bedrock-native only | Strands, LangGraph, CrewAI, LlamaIndex, and others |

**Decision for our single bounded tool** (`get_player_stats`, already implemented locally
in `app/services/agent_service.py`): use only **Gateway** (exposes the tool, replacing the
"action group" concept) and **Runtime** (hosts/invokes the agent). Memory, Identity,
Policy, and Observability all solve real problems AgentCore is built for — conversation
memory across sessions, per-user credential brokerage, tool-access governance, OpenTelemetry
tracing — but none of them apply to a single stateless stats lookup. **Lesson, echoing
§9's IaC point:** a more powerful/modular platform doesn't obligate you to use every piece
of it; scope to what the actual use case needs, the same discipline as picking CDK L1 vs.
L2 constructs or OpenSearch Serverless vs. a full self-managed cluster.

**Status:** plan updated, nothing built yet — this pivot happened at the "about to
implement" moment, before any AgentCore API calls, CLI commands, or resources. When Phase 7
resumes, start from AgentCore's own getting-started docs for Gateway and Runtime rather
than assuming the Classic Agents CLI/API knowledge transfers directly — it's a different
service, not a renamed one, and we've been burned once already this session (§3, §7) by
assuming stale documentation matches the current API surface.

---

## 16. Building Phase 7 on Bedrock AgentCore — from zero to a working (throttled) agent

Picked this back up the same day. Rather than trust any single blog post's code sample,
verified the actual installed API surface directly — `uv run --with bedrock-agentcore
--with strands-agents python -c "..."` to inspect `BedrockAgentCoreApp` and Strands'
`Agent` class before writing a line of real code. This caught two things blog posts
either got subtly wrong or didn't mention at all (see below), for free, before wasting a
deploy cycle on them.

### Skipped Gateway entirely — and skipped the `agentcore-cli` tool too
Confirmed the plan from §15: our one bounded tool doesn't need AgentCore Gateway. Built it
as a plain Strands `@tool`-decorated function wrapping the existing `get_player_stats`
logic, running in the same process as the agent — no separate Gateway resource, no Lambda,
no MCP server. Also skipped the new `agentcore-cli` (npm package `@aws/agentcore`) that's
superseded the older `bedrock-agentcore-starter-toolkit` — it's TUI-first with no
documented non-interactive mode, which doesn't fit a scripted/CI-style workflow. Went
straight to `aws bedrock-agentcore-control create-agent-runtime` instead, the same
direct-API approach that worked well for Guardrails, OpenSearch Serverless, and ECS
Express Mode all session — `--generate-cli-skeleton input` gave an authoritative,
version-matched example of the exact request shape, more reliable than any blog post for
a service this new.

### Two deployment paths, and the first one hit an undocumented (to us) hard limit
`create-agent-runtime`'s `agentRuntimeArtifact` supports either `codeConfiguration` (zip
on S3, dependencies installed at cold-start) or `containerConfiguration` (pre-built image
from ECR). Tried code-based first since it skips Docker entirely — but it failed with:
```
RuntimeClientError: Runtime initialization time exceeded. Please make sure that
initialization completes in 30s.
```
Strands' own dependency tree (opentelemetry, mcp, cryptography, httpx, and more) is too
heavy to `pip install` from a cold start inside a 30-second budget. **Pivoted to the
container path** — same Docker + ECR pattern already built out in Phases 10 and 14, just
targeting a different AWS consumer of the image. One new constraint: AgentCore Runtime
requires **arm64** images specifically, built here with
`docker buildx build --platform linux/arm64`. Also learned mid-pivot that
**`update-agent-runtime` cannot change the artifact type** once created
(`codeConfiguration` ↔ `containerConfiguration` — `ValidationException: Agent artifact
type cannot be updated`) — had to `delete-agent-runtime` and `create-agent-runtime` fresh
rather than migrate the existing one.

### The concurrency bug — a real design mistake, not a platform quirk
First container-based invoke reached the agent code (no more init-timeout) but failed
differently:
```
ConcurrencyException: Agent is already processing a request. Concurrent invocations are
not supported.
```
The actual bug: `agent.py` built the Strands `Agent` **once at module import time** and
reused that single instance across every request the warm container received — but
Strands agents hold per-conversation state and aren't safe to share across concurrent
invocations of the same process. Fix: construct a fresh `Agent(...)` **inside** the
`@app.entrypoint` function, once per request, instead of module-level. This is the same
category of mistake as sharing a database connection or a non-thread-safe client across
requests in any web framework — AgentCore Runtime didn't do anything unusual here, our
code just assumed single-request-at-a-time without that being a guarantee.

### Verified — hit the exact same known quota, from a third API surface
After the concurrency fix, the container-based agent ran cleanly end-to-end: no init
timeout, no concurrency error, task role credentials worked with zero access keys
(matching the pattern already proven in Phase 14). It failed only on the actual Bedrock
call:
```
ModelThrottledException: An error occurred (ThrottlingException) when calling the
ConverseStream operation (reached max retries: 4): Too many tokens per day, please wait
before trying again.
```
This is the identical account-wide daily token quota from §3/§8/§14 — now confirmed
against a **third** distinct Bedrock API surface (`InvokeModel`, `InvokeModelWithResponseStream`
via ECS, and now `ConverseStream` via Strands' Bedrock model provider), reinforcing that
this is genuinely one account-level budget shared across every code path that reaches
Bedrock, not something specific to any one client library or invocation style.

### Cost model — different from OpenSearch Serverless and ECS, no forced teardown needed
AgentCore Runtime bills on **active consumption**, not continuous provisioning: CPU is
billed only while the agent is actively processing (idle time waiting on an LLM/tool
response doesn't accrue CPU charges), though memory bills for the full duration a session
stays alive (`idleRuntimeSessionTimeout`, 900s by default) even during idle waits within
that session. There's no standing reserved compute the way an ALB + Fargate task or an
OpenSearch Serverless collection has — a runtime *definition* sitting unused costs
nothing, much closer to Bedrock/S3's pay-per-use model than to Phase 12/14's
continuously-billed infrastructure. **Practical result: no urgency to delete the
AgentCore Runtime or its ECR image after this verification**, unlike OpenSearch
Serverless (§7) or the ECS Express service (§14).

---

## 17. Retrospective: would starting with AgentCore have changed much else?

Worth asking directly, since it's exactly the kind of architectural-reasoning question an
interviewer would raise: if Phase 7 had targeted AgentCore from the very beginning
(instead of following the PRD's Classic Agents design until the pivot in §15), how much of
the rest of the build would have looked different?

**Answer: surprisingly little — mostly timing/ordering, not architecture.** The reason is
almost entirely a credit to how the project was scoped, not luck:

- **RAG, storage, and deployment are clean, separate concerns behind interfaces**
  (`VectorStoreBackend`, `StorageBackend`), never coupled to the agent layer. The Titan
  Embeddings → OpenSearch Serverless → S3 pipeline, Guardrails, and the ECS Express Mode
  deployment of the main Streamlit+FastAPI app are all orthogonal to which agent framework
  handles tool-calling.
- **Neither Classic Agents nor AgentCore is something you import into the app process** —
  both are separate managed services invoked over the network. So `/agent-query` in
  `app/main.py` would have looked almost identical either way: call a boto3 client, get a
  response, return it. Only the specific client (`bedrock-agent-runtime` vs.
  `bedrock-agentcore`) would differ.

**What genuinely would have shifted, all timing/ordering rather than structural:**
- Docker/ECR/arm64 experience would have been built *first* via the agent container
  (Phase 7), then reused for Phase 14's ECS Express Mode — the reverse of what actually
  happened (main-app container skills from Phase 10 got reused for the agent in §16).
- "Bedrock Agents Classic is closed to new customers" would likely have been discovered as
  the **first** closed-service surprise instead of the second — meaning we might not yet
  have had the "check if a service still accepts new customers before building against
  it" instinct that the App Runner incident (§13) taught us, and could plausibly have hit
  it live via a failed `create-agent` call rather than catching it proactively via docs.
- The specific IAM permission requests would have landed in a different order
  (`BedrockAgentCoreFullAccess` before `AmazonECS_FullAccess`), though the total scope of
  grants ends up about the same either way.

**What would have been identical no matter what: the account-wide Bedrock token quota.**
This was proven to be a shared, account-level limit — not framework- or client-specific —
by hitting it through three unrelated API surfaces across three different phases
(`InvokeModel` directly, `InvokeModelWithResponseStream` via the ECS-deployed app, and
`ConverseStream` via Strands/AgentCore). Building the agent first would not have avoided
it or changed how it presented.

**Interview framing:** the fact that a fairly significant framework pivot (Classic Agents
→ AgentCore, discovered mid-project) touched only one phase's implementation, not the
surrounding architecture, is itself the strongest evidence that the pluggable-backend /
clean-separation-of-concerns design (§1) was the right call — good architecture is
measured by how little a component swap ripples outward, not by getting every choice
right on the first try.

---

## 18. Cross-cutting lessons for the interview

1. **IAM debugging loop:** attempt → read the exact action name from
   `AccessDeniedException` → grant precisely that. Faster and more accurate than
   pre-guessing a policy.
2. **Two different Bedrock throttle classes exist** and need different responses:
   request-rate (`"Too many requests"`, retry shortly) vs. daily token quota
   (`"Too many tokens per day"`, needs real time or a quota increase — retrying
   immediately does nothing).
3. **Managed-API pay-per-call services vs. provisioned bills-while-it-exists
   infrastructure** is the single most important AWS cost distinction in this whole
   build. OpenSearch Serverless and ECS Express Mode (ALB + Fargate task) are in the
   second category and need active teardown discipline; Bedrock/S3/Guardrails are in the
   first and can be left alone indefinitely at near-zero cost.
4. **Console UX changes fast** — both the Bedrock "Model access" page retirement and the
   IAM access-key creation nudge toward SSO happened without us expecting them; always be
   ready to adapt the *documented* flow to whatever the console actually shows.
5. **Pluggable backend interfaces pay for themselves immediately** in a project like this:
   every "swap to the real AWS service" phase was a `.env` flag flip plus one new file,
   never a rewrite of calling code.
6. **A guardrail can be tested even when generation is throttled** — because guardrail
   input-blocking short-circuits before full model generation, it's a cheap way to prove
   wiring correctness independent of token budget.
7. **Not every AWS quota has a simple time-based reset, and not every quota is
   self-service adjustable.** "Too many tokens per day" didn't clear after a full 24h
   wait, and Service Quotas showed most Bedrock inference quotas as "Not Available" for
   this account — the real next lever is an AWS Support case, not more waiting.
8. **"Create manually first, then automate with IaC" is a genuine debugging strategy**,
   not just a sequencing preference — having already built OpenSearch Serverless by hand
   made every CDK `Cfn*` property immediately recognizable, isolating "is this a CDK
   mistake" from "do I understand this AWS service" as two separate questions instead of
   one tangled one.
9. **IaC tooling has its own IAM footprint, separate from the workload it deploys.**
   `cdk bootstrap` needed `cloudformation:*`, scoped IAM role management, `ecr:*`, and
   `ssm:*` — none of which the *application* itself needs at runtime. Don't conflate
   "permissions to deploy infrastructure" with "permissions the deployed workload uses."
10. **When several unrelated-looking services all fail in similar "not allowed" ways on
    a brand-new account, check the account tier itself first.** A whole day of what looked
    like independent IAM/quota debugging (Bedrock quota, App Runner subscription) traced
    back to one thing: the account was on AWS's restricted Free Plan the entire time.
11. **Read the platform's own deprecation notices instead of fighting them.** App Runner
    being closed to new customers wasn't a permissions problem to solve — it was AWS
    explicitly naming a replacement (ECS Express Mode) in the same banner. Recognizing
    "this isn't fixable, pivot" is as important a skill as persistent debugging.
12. **A load-balanced deployment has two ports/paths that matter, and they're not the
    same one:** the container's *internal* API health check (FastAPI's `/health` on
    `localhost:8000`) is unreachable from outside the task; the ALB needs a health check
    path on the *externally exposed* port (Streamlit's built-in `/_stcore/health` on
    8501). Wiring the wrong one silently breaks the health check with no obvious error
    pointing at the actual mismatch.
13. **`DependencyViolation` on a resource deletion, right after deleting whatever used
    it, is usually a race condition to wait out — not a stuck deployment.** ECS's own
    Express Mode teardown hit and auto-resolved exactly this (a security group waiting on
    its ALB's network interface to detach) within about a minute, without any manual
    intervention.
14. **"Is this service still open to new customers?" is worth asking before building
    against any AWS service named in an older spec or PRD, not just when something fails.**
    Both App Runner and Bedrock Agents Classic turned out to be closed to new customers —
    caught the second one proactively by checking docs first, rather than discovering it
    mid-implementation like the first.
15. **A more modular/powerful replacement service doesn't mean using all of it.**
    AgentCore offers seven-ish composable primitives; our use case ended up needing just
    one (Runtime — Gateway turned out to be unnecessary too, once actually built, since a
    single in-process tool doesn't need a separate resource to expose it). Scoping to
    what's actually needed, not what's available, is the same discipline that applies to
    CDK L1 vs. L2 constructs and managed vs. self-hosted infrastructure choices generally.
16. **Inspecting the installed library's real API directly beats trusting any single
    blog post**, especially for something this new. A one-line `uv run --with <pkg>
    python -c "..."` to check a class's actual `__init__`/method signatures caught the
    correct entrypoint/decorator shape before writing real code, and cost less time than
    guessing wrong and debugging a deploy failure instead.
17. **Sharing a stateful client/object across concurrent requests is a general web-service
    bug, not an AWS-specific one** — a module-level Strands `Agent` instance reused across
    invocations broke under concurrency the same way a shared DB connection or non-thread-
    safe client would in any framework. The fix (construct fresh per-request) is generic
    web-service hygiene, not something particular to AgentCore.
18. **The same root-cause quota surfacing through a third, completely different API call**
    (`InvokeModel` → `InvokeModelWithResponseStream` → `ConverseStream`) is strong
    confirmation it's a genuine account-level budget, not a bug isolated to one client or
    code path — useful for ruling out "maybe it's this specific SDK" as a hypothesis.
19. **A good architecture is measured by how little a component swap ripples outward, not
    by getting every choice right the first time.** Pivoting Phase 7's entire agent
    framework mid-project (Classic Agents → AgentCore) touched only that phase's
    implementation, not the RAG pipeline, storage, or deployment — a direct payoff of
    keeping those concerns behind clean interfaces (§1) rather than coupled to whichever
    agent service happened to be current when each part was built.
