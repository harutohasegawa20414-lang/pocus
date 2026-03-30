#!/bin/bash
# POCUS 起動スクリプト

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# .env から環境変数を読み込む
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

# Docker Desktop が起動するまで待機
echo "Docker の起動を待機中..."
for i in $(seq 1 30); do
  if docker info >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# PostgreSQL コンテナ起動
echo "データベースを起動中..."
cd "$PROJECT_DIR"
docker compose up -d db

# DB が ready になるまで待機
echo "データベースの準備を待機中..."
for i in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U "${POSTGRES_USER:-pocus}" -d "${POSTGRES_DB:-pocusdb}" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# uvicorn 起動
echo "サーバーを起動中..."
exec uvicorn tas.api.main:app \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-6002}" \
  --workers "${UVICORN_WORKERS:-1}"
