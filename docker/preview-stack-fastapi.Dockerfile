# Trusted operator image; project code is bind-mounted readonly at runtime.
# No user-generated requirements.txt or Dockerfile is executed during build.
FROM python:3.12-slim
RUN pip install --no-cache-dir "fastapi==0.128.2" "uvicorn==0.40.0" "psycopg[binary]>=3.2,<4" "SQLAlchemy>=2.0,<3"
USER 10001:10001
WORKDIR /workspace
