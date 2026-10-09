#!/usr/bin/env bash
# Dispara el workflow vigente sin modificar el checkout local de Hermes.
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/monitoreo-pr"
mkdir -p "$STATE_DIR"
exec >> "$STATE_DIR/refresh.log" 2>&1
exec 9> "$STATE_DIR/refresh.lock"
if ! flock -n 9; then
    printf '%s Ya hay un disparo en curso; se omite este intento.\n' "$(date -Is)"
    exit 0
fi
printf '%s Solicitando actualización de master.\n' "$(date -Is)"
if ! command -v gh >/dev/null 2>&1; then
    echo 'ERROR: falta GitHub CLI (gh).'
    exit 1
fi
if ! timeout 30s gh auth status --hostname github.com >/dev/null 2>&1; then
    echo 'ERROR: GitHub CLI no tiene autenticación válida para github.com.'
    exit 1
fi
if timeout 60s gh workflow run deploy-pages.yml --repo jrhernandezp/monitoreo-pr --ref master; then
    printf '%s Disparo aceptado. Verificar build y deploy en GitHub Actions.\n' "$(date -Is)"
else
    echo 'ERROR: GitHub rechazó el disparo o agotó el tiempo de espera.'
    exit 1
fi
