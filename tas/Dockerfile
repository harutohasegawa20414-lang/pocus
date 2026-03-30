FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 非rootユーザーで実行
RUN addgroup --system app && adduser --system --group app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY tas/ tas/

ARG PORT=8080
ENV PORT=${PORT}
ENV WORKERS=1
EXPOSE ${PORT}

USER app

CMD exec uvicorn tas.api.main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS}
