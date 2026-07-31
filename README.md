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
- [ ] Phase 1 — AWS IAM + Bedrock model access (in progress — awaiting `playbookiq-dev` access key)
- [x] Phase 2 — Synthetic sports data
- [x] Phase 3 — Pluggable storage interface (local)
- [x] Phase 4 — Real Bedrock model invocation (code + mocked tests done; live smoke test pending Phase 1)
- [x] Phase 5 — Embeddings + local RAG (code + tests done; live ingestion pending Phase 1)
- [ ] Phase 6 — Bedrock Guardrails
- [x] Phase 7 — Bedrock Agents / Action Groups (local tool contract done; real Bedrock Agent pending)
- [x] Phase 8 — FastAPI service layer
- [x] Phase 9 — Streamlit frontend (Carbon theme)
- [ ] Phase 10 — Containerization
- [ ] Phase 11 — Real S3 swap-in
- [ ] Phase 12 — Real OpenSearch Serverless + Bedrock Knowledge Base
- [ ] Phase 13 — AWS CDK infrastructure as code
- [ ] Phase 14 — AWS App Runner deployment

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
