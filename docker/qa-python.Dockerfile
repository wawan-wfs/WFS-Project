# Optional operator QA image only. Never included in the API/worker compose services.
FROM python:3.12-slim
RUN pip install --no-cache-dir fastapi==0.128.2 httpx==0.28.1 pytest==8.4.2 uvicorn==0.40.0
USER 10001:10001
WORKDIR /workspace
