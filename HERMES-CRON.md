# Actualización permanente del dashboard en Vendetta

## Instrucción para Hermes

Mantener el dashboard de `jrhernandezp/monitoreo-pr` actualizado cada 15 minutos.
Usar el workflow versionado `.github/workflows/deploy-pages.yml` de `master`.
No sustituirlo por un workflow antiguo ni publicar snapshots locales de
`dashboard.html`. El workflow recoge las noticias y publica `index.html` y
`dashboard.html` con el mismo contenido; conserva los nombres únicos de los
artefactos por ejecución e intento.

En Vendetta, ubicar el checkout del repositorio y actualizarlo mediante
`git pull --ff-only`. Si hay cambios locales o diverge la rama, detenerse e
informar sin descartarlos. Confirmar que el checkout corresponde a `master`.
Verificar GitHub CLI (`gh`), `flock`, `timeout`, `crontab` y el servicio cron.
La cuenta de `gh` debe tener permiso para disparar Actions en este repositorio.
No copiar credenciales a archivos versionados ni a los registros.

Desde el checkout, ejecutar:

```bash
bash install-dashboard-cron.sh
bash refresh-dashboard.sh
crontab -l
gh run list --repo jrhernandezp/monitoreo-pr --workflow deploy-pages.yml --limit 5
```

El instalador deja una única entrada propia, identificada con
`# monitoreo-pr-dashboard-15m`, en los minutos **08, 23, 38 y 53** de cada hora.
Conserva las demás entradas y respalda el crontab anterior en
`~/.local/state/monitoreo-pr/` (o `$XDG_STATE_HOME/monitoreo-pr/`). Se puede volver
a ejecutar sin duplicar su entrada. No agrega trabajo al iniciar sesión: cron
es quien ejecuta el script aunque Telegram o la conversación de Hermes estén
cerrados. Verificar que el servicio cron esté activo y habilitado al arrancar.

Si Hermes tiene otra tarea para este mismo dashboard, identificarla y sustituir
solo esa tarea por esta entrada; no mantener un segundo actualizador ni borrar
tareas ajenas. No hacer commits automáticos de HTML ni sobrescribir el workflow.
El script siempre dispara la versión de `master` alojada en GitHub, incluso si
el checkout local del servidor no recibe cada nuevo commit.

## Comprobación obligatoria

Confirmar una ejecución manual con `build` y `deploy` exitosos. Después comprobar
dos ejecuciones de tipo `workflow_dispatch` originadas por cron en dos intervalos
consecutivos, y la fecha visible en Pages. No informar que quedó instalado ni
que funciona automáticamente antes de estas verificaciones.

El registro de solicitudes está en `~/.local/state/monitoreo-pr/refresh.log`
(o `$XDG_STATE_HOME/monitoreo-pr/refresh.log`). Un disparo aceptado no confirma
que la publicación terminó: revisar el resultado en Actions. Ante fallos,
informar el error; no reemplazar la página con datos vacíos ni reintentar en bucle.

## Alcance y persistencia

Los scripts e instrucciones permanecen en Git. El crontab instalado en Vendetta
persiste tras cerrar Hermes y tras reiniciar el servidor. Vendetta debe estar
encendido, conectado, con cron activo y autenticación válida de `gh`. GitHub
todavía puede encolar o fallar al ejecutar un disparo manual; esta configuración
solicita actualizaciones cada 15 minutos, sin prometer publicaciones a tiempo
exacto. El `schedule` de GitHub permanece como respaldo.

Guardar esta regla en la memoria persistente de Hermes y en su registro de
mantenimiento del dashboard, indicando la ruta real del checkout, el usuario
dueño del crontab y las ejecuciones verificadas. No crear una tarea de ChatGPT
para sustituir este cron.
