#!/bin/sh
set -e

if [ "$1" = "evalrunner" ]; then
  # Prompt eval runner (docker-compose.evals.yml). No database: it runs the
  # capture pipeline on test cases and talks to NIM.
  echo "Starting eval runner..."
  exec uvicorn app.prompts.runner_api:app --host 0.0.0.0 --port 8090 --workers 1
fi

if [ "$1" = "worker" ]; then
  echo "Starting job worker..."
  exec python -m procrastinate --app=app.jobs.queue.app worker --concurrency=1
fi

echo "Running database migrations..."
alembic upgrade head
python -c "from app.jobs.queue import apply_schema; apply_schema()"

echo "Starting application..."
exec uvicorn app:app --host 0.0.0.0 --port 8082 --workers 2
