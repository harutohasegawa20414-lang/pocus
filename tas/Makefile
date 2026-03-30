.PHONY: dev stop

# フロントエンド (Vite :6001) + バックエンド (uvicorn :6002) を同時起動
# Ctrl+C で両方終了
dev: stop
	@trap 'kill 0' EXIT; \
	  .venv/bin/uvicorn tas.api.main:app --host 0.0.0.0 --port 6002 --reload & \
	  cd ui && npm run dev

# 両ポートのプロセスを終了
stop:
	@-lsof -ti:6001,6002 | xargs kill -9 2>/dev/null || true
	@sleep 0.5
