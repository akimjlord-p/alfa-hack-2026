#!/bin/sh
set -eu
cd /opt/akimai
umask 077
chmod 600 .env.production
if ! grep -q '^POSTGRES_PASSWORD=' .env.production; then
    printf '\nPOSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)" >> .env.production
fi
docker compose --env-file .env.production -f docker-compose.server.yml up --build -d
docker compose --env-file .env.production -f docker-compose.server.yml ps
curl --fail --silent --show-error http://127.0.0.1:8088/api/health
