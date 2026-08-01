# PlaybookIQ

Enterprise sports-intelligence RAG/agent demo (fictional client "Sportsnexa") built as a
hands-on tour through AWS Bedrock, OpenSearch Serverless, S3, Guardrails, Bedrock Agents,
Docker, CDK, and App Runner. See `PlaybookIQ_PRD.pdf` for the original spec.

Built phase-by-phase, skill-by-skill, following the plan in
`C:\Users\admin\.claude\plans\i-need-to-build-zesty-spark.md`. Each phase starts real
(Bedrock model calls) or local-first (vector store, storage) and gets swapped for the
real AWS service in its own dedicated phase, so every AWS skill in the PRD gets
hands-on practice.

## Status

- [x] Phase 0 — Scaffolding, git, environment
- [x] Phase 1 — AWS IAM + Bedrock model access (playbookiq-dev user created, Bedrock access granted; account is on a new-account daily token throttle for invoke_model)
- [x] Phase 2 — Synthetic sports data
- [x] Phase 3 — Pluggable storage interface (local)
- [x] Phase 4 — Real Bedrock model invocation (code + mocked tests done; live invoke_model blocked by daily token quota, see below)
- [x] Phase 5 — Embeddings + local RAG (code + tests done; live ingestion blocked by the same quota)
- [x] Phase 6 — Bedrock Guardrails (created + published + verified live: PII prompt correctly blocked)
- [x] Phase 7 — Bedrock Agents / Action Groups (local tool contract done; real Bedrock Agent deferred until quota clears)
- [x] Phase 8 — FastAPI service layer
- [x] Phase 9 — Streamlit frontend (Carbon theme)
- [x] Phase 10 — Containerization (built + ran locally, verified end-to-end in browser)
- [x] Phase 11 — Real S3 swap-in (bucket created, data uploaded, verified)
- [ ] Phase 12 — Real OpenSearch Serverless + Bedrock Knowledge Base (collection, policies, and k-NN index were created and verified, then torn down to stop billing before ingestion could complete — see docs)
- [x] Phase 13 — AWS CDK infrastructure as code (bootstrap → synth → deploy → verify → destroy all done live; S3 bucket + OpenSearch Serverless collection provisioned as code and torn down within ~7 minutes)
- [ ] Phase 14 — AWS App Runner deployment

**Known blocker:** the AWS account is hitting `ThrottlingException: Too many tokens per day`
on Bedrock `invoke_model` (new-account quota). Guardrail-blocked requests still succeed
(near-zero token cost), proving the wiring is correct — full generation calls need either
a daily quota reset or a Service Quota increase request. Also note: the PRD's literal
`claude-3-5-sonnet-20240620` model ID is gone from the catalog; newer Claude models need
an inference profile ID (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`, etc.), and the
very newest model (`claude-sonnet-5`) is access-denied separately from the rest.

## Documentation

- [`docs/RESUME_HERE.md`](docs/RESUME_HERE.md) — current status and exact next steps
- [`docs/LEARNING_JOURNAL.md`](docs/LEARNING_JOURNAL.md) — full AWS learning writeup:
  every service used, every real error hit and its fix, and interview talking points
- [`CLAUDE.md`](CLAUDE.md) — quick orientation for working in this codebase

## Local development

```powershell
uv sync
Copy-Item .env.example .env   # then fill in AWS profile/region/model IDs
uv run uvicorn app.main:app --reload --port 8000
uv run streamlit run app/ui.py
```

## Region

Everything in this project runs in `us-east-1`. Do not mix regions across phases —
Bedrock model access and OpenSearch Serverless collections are both region-scoped.
