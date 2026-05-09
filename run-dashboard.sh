#!/bin/bash
# Dashboard Municipal — Lanzador silencioso
# José — Presencia PR

cd /home/jrhernandez/monitoreo-municipal
source .venv/bin/activate

# Generar dashboard
python3 dashboard.py > /tmp/dashboard-log.txt 2>&1

# Abrir Chrome directamente con el archivo
/usr/bin/google-chrome --new-window "file:///home/jrhernandez/monitoreo-municipal/dashboard.html" &
