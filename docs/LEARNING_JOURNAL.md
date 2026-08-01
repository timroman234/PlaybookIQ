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

## 8. Docker — a lesson in resource constraints, not AWS

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

## 9. FastAPI + Streamlit — the app layer

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

## 10. Cross-cutting lessons for the interview

1. **IAM debugging loop:** attempt → read the exact action name from
   `AccessDeniedException` → grant precisely that. Faster and more accurate than
   pre-guessing a policy.
2. **Two different Bedrock throttle classes exist** and need different responses:
   request-rate (`"Too many requests"`, retry shortly) vs. daily token quota
   (`"Too many tokens per day"`, needs real time or a quota increase — retrying
   immediately does nothing).
3. **Managed-API pay-per-call services vs. provisioned bills-while-it-exists
   infrastructure** is the single most important AWS cost distinction in this whole
   build. OpenSearch Serverless and (later) App Runner are in the second category and
   need active teardown discipline; Bedrock/S3/Guardrails are in the first and can be
   left alone indefinitely at near-zero cost.
4. **Console UX changes fast** — both the Bedrock "Model access" page retirement and the
   IAM access-key creation nudge toward SSO happened without us expecting them; always be
   ready to adapt the *documented* flow to whatever the console actually shows.
5. **Pluggable backend interfaces pay for themselves immediately** in a project like this:
   every "swap to the real AWS service" phase was a `.env` flag flip plus one new file,
   never a rewrite of calling code.
6. **A guardrail can be tested even when generation is throttled** — because guardrail
   input-blocking short-circuits before full model generation, it's a cheap way to prove
   wiring correctness independent of token budget.
