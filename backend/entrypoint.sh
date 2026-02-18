#!/bin/sh
set -e

if [ "${USE_ALEMBIC_MIGRATIONS}" = "true" ]; then
    echo "Running Alembic migrations..."
    /app/.venv/bin/alembic upgrade head
fi

exec "$@"
