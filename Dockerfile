# PlaybookIQ container: runs FastAPI (Phase 8) + Streamlit (Phase 9) in one process
# group, sized for a single AWS App Runner service (Phase 14). Streamlit calls the
# FastAPI backend over http://localhost:8000 inside this same container.

FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.11-slim
COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

COPY app/ ./app/
COPY data/ ./data/
COPY styles.py ./
COPY .streamlit/ ./.streamlit/
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8501
ENV PYTHONUNBUFFERED=1

CMD ["./docker-entrypoint.sh"]
