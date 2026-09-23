#!/bin/sh
set -eu
exec gunicorn --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 4 --timeout 60 --access-logfile - 'app:create_app()'
