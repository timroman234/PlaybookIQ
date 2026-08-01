# AgentCore Runtime requires arm64 container images.
# Build from the repo root so this can reuse app/services/agent_service.py directly:
#   docker buildx build --platform linux/arm64 -f agentcore/Dockerfile -t <tag> --push .
FROM python:3.12-slim

WORKDIR /app

COPY agentcore/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agentcore/agent.py ./
COPY app/__init__.py ./app/__init__.py
COPY app/services/__init__.py ./app/services/__init__.py
COPY app/services/agent_service.py ./app/services/agent_service.py
COPY data/raw/players.json ./data/raw/players.json

EXPOSE 8080

CMD ["python", "agent.py"]
