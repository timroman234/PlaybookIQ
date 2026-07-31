#!/bin/sh
set -e

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &

exec uv run streamlit run app/ui.py --server.port=8501 --server.address=0.0.0.0
