# Observador del Noreste — Puerto Rico

Dashboard de noticias de 15 municipios: San Juan, Carolina, Trujillo Alto,
Caguas, Luquillo, Canóvanas, Fajardo, Loíza, Río Grande, Ceiba, Naguabo,
Humacao, Cataño, Vieques y Culebra.

## Instalación y uso

Requiere Python 3.9 o superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python dashboard.py
```

Se genera `index.html` con la plantilla `templates/dashboard.html`.
Usa `python dashboard.py --open` para abrirlo. Las fechas siempre usan
la hora de Puerto Rico, aunque el servidor esté en UTC.

News API es opcional: guarda `NEWS_API_KEY` en el entorno o en `.env`.
Las fuentes sin configuración y las solicitudes fallidas se indican como
advertencia o error, no como fuentes funcionando.

## Publicación

GitHub Actions prueba el código, recoge las noticias, genera el dashboard y
publica los archivos estáticos en Pages. La programación solicita ejecuciones
cada 15 minutos; GitHub puede retrasarlas. También se ejecuta con pushes a
`master` o manualmente con `workflow_dispatch`.

Si usas News API en Actions, configura el secreto de repositorio
`NEWS_API_KEY`. No es necesario para RSS.
El estado de noticias vistas se conserva mediante caché entre ejecuciones.
La caché puede desaparecer, en cuyo caso las noticias se marcarán como nuevas.
Los datos del estado nunca se publican en Pages.

`dashboard.html` y `index.html` se publican con el mismo contenido.
La recarga de la vista cada 15 minutos no garantiza por sí misma una nueva
recolección: la fecha visible corresponde a la generación del archivo.
Si fallan todas las fuentes, el flujo falla y conserva la última publicación.

## Fuentes y fechas

Se consultan RSS y Google News con un máximo de seis solicitudes simultáneas.
Los enlaces de seguimiento se normalizan y se fusionan titulares idénticos.
Se muestran los dos últimos días del calendario local; se excluyen fechas
desconocidas o futuras. Las noticias sin hora mantienen su fecha sin inventar
una hora. El scraping de portada no asigna la hora de consulta como si fuese
la publicación.

Facebook mediante navegador depende de un scraper externo local, que no
está incluido en este repositorio. Puede configurarse con `FACEBOOK_SCRAPER`
y `FACEBOOK_PYTHON`; en Actions se muestra como no configurado. Las búsquedas
RSS de publicaciones indexadas por Google siguen disponibles.

## Mantenimiento

El aviso de antigüedad se basa en la última recolección exitosa: advertencia
desde 30 minutos y alerta desde 45, actualizadas cada minuto en el navegador.
El detalle de fuentes muestra el motivo del fallo, la última respuesta
exitosa y los artículos recientes únicos aportados a la tabla (dos días).
El historial empieza con esta versión; no reconstruye éxitos anteriores.

Ante un fallo parcial se conservan los artículos anteriores de la fuente
fallida, dentro del mismo período de dos días, marcados como CONSERVADA y
con su fecha de publicación y última verificación originales. No aparecen
como nuevos ni en el banner urgente. Una fuente que responde correctamente
con cero artículos no utiliza este respaldo. Si todas fallan, se mantiene
la protección que conserva la última publicación. El respaldo y el historial
se guardan en el mismo state.json privado y dependen de la caché de Actions;
no se garantiza recuperar noticias si la caché ha desaparecido.

La clasificación excluye referencias explícitas a localidades extranjeras
y nombres como Carolina Panthers o Soge Culebra, sin descartar otras
menciones locales en el mismo texto. Sigue siendo una heurística.

`run-dashboard.sh` trabaja desde la carpeta del repositorio.
`cleanup_daily.sh` reinicia los marcadores vistos sin borrar la última página
ni enviar archivos de estado privados a GitHub.
La generación y el estado se escriben de forma atómica para evitar archivos
parciales. El estado se guarda después de generar el HTML correctamente.
