#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

python -c "from app.jobs.queue import apply_schema; apply_schema()"

if [ "$1" = "worker" ]; then
  echo "Starting job worker..."
  exec python -m procrastinate --app=app.jobs.queue.app worker --concurrency=1
fi

echo "Starting application..."
exec uvicorn app:app --host 0.0.0.0 --port 8082 --workers 2
