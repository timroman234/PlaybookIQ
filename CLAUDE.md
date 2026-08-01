# PlaybookIQ

Enterprise sports-intelligence RAG/agent demo (fictional client "Sportsnexa"), built
phase-by-phase as a hands-on AWS skills learning vehicle ahead of a job interview. The app
itself is secondary — the point is deliberate, verified, hands-on practice with every AWS
service in the stack.

**Before touching AWS resources or making architecture calls, read:**
- `docs/RESUME_HERE.md` — current status and exact next steps
- `docs/LEARNING_JOURNAL.md` — everything learned so far, including every real error hit
  and its fix (read before re-debugging something already solved)
- `PlaybookIQ_PRD.pdf` — original spec this build is adapting

## Tech stack

Python 3.11+, `uv` (package manager, always use `uv run <cmd>` — never manually activate
`.venv`), FastAPI, Streamlit, boto3, opensearch-py, pytest, ruff. Region is pinned to
`us-east-1` everywhere — never mix regions across AWS resources in this project.

## Architecture pattern — pluggable backends

Two interfaces make "swap local for real AWS" a `.env` flag flip, not a rewrite:
- `StorageBackend` (`app/services/storage_service.py`): `LocalFileStorage` ↔ `S3Storage`
  (`STORAGE_BACKEND=local|s3`)
- `VectorStoreBackend` (`app/services/vector_store.py`): `LocalVectorStore` ↔
  `OpenSearchServerlessBackend` (`VECTOR_STORE_BACKEND=local|opensearch_serverless`)

When adding a new AWS-backed capability, follow this same pattern: define the interface,
ship a free/local implementation first, verify the logic against it, then add the real-AWS
implementation behind the same contract.

## Running locally

```powershell
uv sync
uv run uvicorn app.main:app --reload --port 8000    # terminal 1
uv run streamlit run app/ui.py                       # terminal 2
```

Or containerized (runs both together):
```powershell
docker build -t playbookiq:local .
docker run --rm -p 8501:8501 --env-file .env playbookiq:local
```

## AWS account

- Profile: `playbookiq` (dedicated IAM user `playbookiq-dev`, not the account's `default`
  profile — that belongs to a different project). Always pass `--profile playbookiq
  --region us-east-1` on `aws` CLI calls, or rely on `.env`'s `AWS_PROFILE`/`AWS_REGION`
  (loaded via `python-dotenv` in scripts and the app).
- Model IDs in `.env` are the current verified-working ones for this account — **do not**
  revert to the PRD's literal `claude-3-5-sonnet-20240620` ID; it's gone from the catalog.
  Newer models need an inference profile ID (`us.anthropic....`), not a bare model ID.
- **Cost discipline:** OpenSearch Serverless and (later) App Runner bill continuously while
  they exist, unlike Bedrock/S3/Guardrails which are pay-per-call. Never leave either
  running between work sessions — create, verify, tear down. See `docs/RESUME_HERE.md` for
  exact teardown commands.

## Conventions

- No comments unless explaining a non-obvious *why* (a workaround, a hidden constraint) —
  never restate what the code already says.
- Real AWS calls live in `scripts/smoke_test_*.py` (manual verification, costs real
  tokens/pennies) — never in the `pytest` suite. Unit tests mock boto3 clients via
  `unittest.mock.patch` on the module-level `boto3` import; zero real AWS calls in `uv run
  pytest`.
- `uv run ruff check .` should pass clean before committing.
- Streamlit + IBM Carbon theming goes through the `/carbon-streamlit` skill
  (`styles.py` + `.streamlit/config.toml`) — don't hand-write Carbon CSS from scratch.
- Synthetic data only (`data/raw/`, regenerable via
  `scripts/generate_synthetic_data.py`) — no real player/team data, ever.

## Where things stand

See `docs/RESUME_HERE.md` for the authoritative phase-by-phase status table — don't infer
progress from git history alone, since some AWS-side resources (e.g. OpenSearch Serverless)
were deliberately created and then torn down within the same session for cost reasons.
