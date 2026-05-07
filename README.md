# 🗺️ Dashboard de Monitoreo Municipal — Noreste PR

Monitorea noticias de **15 municipios del noreste de Puerto Rico** desde múltiples fuentes y genera un dashboard HTML autónomo.

## Municipios monitoreados

San Juan, Carolina, Trujillo Alto, Caguas, Luquillo, Canóvanas, Fajardo, Loíza, Río Grande, Ceiba, Naguabo, Humacao, Cataño, Vieques, Culebra

## Fuentes

| Fuente | Tipo | Estado |
|--------|------|--------|
| Primera Hora | RSS | ✅ |
| Vocero | RSS | ✅ |
| News API | API | ⚠️ Requiere API key |
| El Nuevo Día | Scraping | ✅ |

## Instalación

```bash
cd ~/monitoreo-municipal
pip install -r requirements.txt
```

## Configuración (opcional)

Para usar News API, copia el archivo .env.example y añade tu API key:

```bash
cp .env.example .env
# Edita .env con tu NEWS_API_KEY
```

Obtén una key gratis en: https://newsapi.org/register

## Uso

```bash
# Generar dashboard
python3 dashboard.py

# Generar y abrir en el navegador
python3 dashboard.py --open
```

Esto genera `dashboard.html` que puedes abrir en cualquier navegador.

## Automatización (cron)

Para que se genere automáticamente cada mañana a las 6:00 AM:

```bash
crontab -e
# Añade esta línea:
0 6 * * * cd ~/monitoreo-municipal && python3 dashboard.py
```
