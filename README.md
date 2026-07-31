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

- [ ] Phase 0 — Scaffolding, git, environment
- [ ] Phase 1 — AWS IAM + Bedrock model access
- [ ] Phase 2 — Synthetic sports data
- [ ] Phase 3 — Pluggable storage interface (local)
- [ ] Phase 4 — Real Bedrock model invocation
- [ ] Phase 5 — Embeddings + local RAG
- [ ] Phase 6 — Bedrock Guardrails
- [ ] Phase 7 — Bedrock Agents / Action Groups
- [ ] Phase 8 — FastAPI service layer
- [ ] Phase 9 — Streamlit frontend (Carbon theme)
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
