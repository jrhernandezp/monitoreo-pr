#!/bin/bash
# Limpieza diaria del dashboard a las 11:59 PM
# Resetea el estado para que al día siguiente solo haya noticias frescas

DASH_DIR="/home/jrhernandez/monitoreo-municipal"
STATE_FILE="$DASH_DIR/data/state.json"
OUTPUT_FILE="$DASH_DIR/index.html"

echo "🧹 Limpieza diaria del dashboard municipal ($(date))"

# Resetear state.json con fecha de mañana
# Así el dashboard.py detectará "nuevo día" mañana
MANANA=$(date -d "+1 day" +%Y-%m-%d)
mkdir -p "$DASH_DIR/data"
cat > "$STATE_FILE" << EOF
{"seen": [], "last_run": null, "source_status": {}, "session_date": "$MANANA"}
EOF
echo "  ✅ State reseteado para el día: $MANANA"

# Generar dashboard placeholder (vacío, indicando que se prepara nuevo día)
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
cat > "$OUTPUT_FILE" << HTMLEOF
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monitoreo Municipal - Noreste PR</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1b2a;
    color: #e0e0e0;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    padding: 20px;
}
.container {
    text-align: center;
    max-width: 600px;
}
h1 { font-size: 32px; color: #ffb347; margin-bottom: 10px; }
p { font-size: 16px; color: #8899aa; line-height: 1.6; }
.spinner { font-size: 48px; margin: 30px 0; animation: pulse 2s ease-in-out infinite; }
@keyframes pulse {
    0% { opacity: 0.4; }
    50% { opacity: 1; }
    100% { opacity: 0.4; }
}
.footer { margin-top: 40px; font-size: 12px; color: #556677; }
</style>
</head>
<body>
<div class="container">
    <div class="spinner">🌅</div>
    <h1>Preparando noticias del día</h1>
    <p>El dashboard se actualizará automáticamente a las 6:00 AM<br>
    con las noticias más recientes de los 15 municipios del noreste de PR.</p>
    <div class="footer">Última limpieza: $TIMESTAMP</div>
</div>
</body>
</html>
HTMLEOF
echo "  ✅ Dashboard placeholder generado"

# Hacer commit y push para GitHub Pages
cd "$DASH_DIR"
git add index.html data/state.json
git commit -m "cleanup: daily reset $(date +'%Y-%m-%d')" --quiet
git push --quiet 2>&1
echo "  ✅ Push a GitHub Pages completado"

echo "✨ Limpieza completada."
