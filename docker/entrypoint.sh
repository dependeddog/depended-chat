#!/usr/bin/env bash
set -euo pipefail

# --------- НАСТРОЙКИ ПО УМОЛЧАНИЮ --------------------------------------------
# Можно переопределить через переменные окружения в docker-compose:
#   DATABASE_URL, APP_MODULE, APP_HOST, APP_PORT, UVICORN_WORKERS, UVICORN_RELOAD
: "${DATABASE_URL:=postgresql+asyncpg://postgres:postgres@db:5432/chat}"
: "${APP_MODULE:=src.main:app}"
: "${APP_HOST:=0.0.0.0}"
: "${APP_PORT:=8000}"
: "${UVICORN_WORKERS:=1}"
: "${UVICORN_RELOAD:=false}"

echo "DATABASE_URL=${DATABASE_URL}"
echo "APP_MODULE=${APP_MODULE}"

if [ "${UVICORN_WORKERS}" != "1" ]; then
  echo "WARNING: UVICORN_WORKERS=${UVICORN_WORKERS} is not supported with in-process WebSocket manager."
  echo "WARNING: Forcing UVICORN_WORKERS=1 to keep realtime delivery working."
  UVICORN_WORKERS=1
fi

# --------- ОЖИДАНИЕ ДОСТУПНОСТИ БД -------------------------------------------
# Не тянем лишние пакеты — проверим сокет через встроенный python.
#python - <<'PY'
#import os, socket, sys
#from urllib.parse import urlparse
#
#url = os.environ['DATABASE_URL']
## Поддержка URL вида postgresql+asyncpg://user:pass@host:port/db
#parsed = urlparse(url.replace('+asyncpg', ''))  # socket не понимает '+asyncpg'
#host = parsed.hostname or 'db'
#port = parsed.port or 5432
#
#for attempt in range(60):
#    try:
#        s = socket.create_connection((host, port), timeout=2)
#        s.close()
#        print(f"DB is reachable at {host}:{port}")
#        sys.exit(0)
#    except OSError:
#        print(f"Waiting for DB at {host}:{port} ... (attempt {attempt+1}/60)")
#    import time; time.sleep(2)
#
#print("ERROR: Database is not reachable, giving up.", file=sys.stderr)
#sys.exit(1)
#PY

# --------- МИГРАЦИИ -----------------------------------------------------------
echo "Running Alembic migrations..."
# Если alembic.ini у вас в корне /app, этого достаточно:
alembic upgrade head

# --------- ЗАПУСК ПРИЛОЖЕНИЯ --------------------------------------------------
echo "Starting Uvicorn..."
if [ "${UVICORN_RELOAD}" = "true" ]; then
  # режим разработки
  exec uvicorn "${APP_MODULE}" --host "${APP_HOST}" --port "${APP_PORT}" --reload --proxy-headers --forwarded-allow-ips="*"
else
  # режим продакшн
  exec uvicorn "${APP_MODULE}" --host "${APP_HOST}" --port "${APP_PORT}" --workers "${UVICORN_WORKERS}" --proxy-headers --forwarded-allow-ips="*"
fi
