#!/usr/bin/env bash
# Instala una sola entrada propia y conserva las demás tareas del usuario.
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
DASH_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
case "$DASH_DIR" in
    *%*|*$'\n'*) echo 'ERROR: la ruta no puede contener % ni saltos de línea.' >&2; exit 1 ;;
esac
for dependency in gh flock timeout crontab; do
    command -v "$dependency" >/dev/null 2>&1 || { echo "ERROR: falta $dependency." >&2; exit 1; }
done
test -s "$DASH_DIR/refresh-dashboard.sh"
timeout 30s gh auth status --hostname github.com >/dev/null 2>&1 || {
    echo 'ERROR: autenticar gh en la cuenta con permiso Actions write antes de instalar.' >&2
    exit 1
}
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/monitoreo-pr"
mkdir -p "$STATE_DIR"
exec 9> "$STATE_DIR/install.lock"
flock 9
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT
if ! crontab -l > "$TEMP_DIR/old" 2> "$TEMP_DIR/error"; then
    if ! LC_ALL=C crontab -l > "$TEMP_DIR/old" 2> "$TEMP_DIR/error"; then
        if ! grep -qi 'no crontab for' "$TEMP_DIR/error"; then
            cat "$TEMP_DIR/error" >&2
            exit 1
        fi
        : > "$TEMP_DIR/old"
    fi
fi
cp "$TEMP_DIR/old" "$STATE_DIR/crontab-before-install-$(date +%Y%m%dT%H%M%S)-$$.txt"
sed '/# monitoreo-pr-dashboard-15m$/d' "$TEMP_DIR/old" > "$TEMP_DIR/new"
# El comando usa comillas POSIX, compatibles con /bin/sh de cron.
QUOTED_PATH="$(printf '%s' "$DASH_DIR/refresh-dashboard.sh" | sed "s/'/'\\\\''/g")"
printf "8,23,38,53 * * * * /bin/bash '%s' # monitoreo-pr-dashboard-15m\n" "$QUOTED_PATH" >> "$TEMP_DIR/new"
crontab "$TEMP_DIR/new"
crontab -l | grep -F '# monitoreo-pr-dashboard-15m'
echo 'Cron instalado para este usuario. Requiere Vendetta encendido, servicio cron activo y acceso a GitHub.'
