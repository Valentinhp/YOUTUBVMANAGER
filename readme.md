# 🎬 YouTubeVManager

**YouTubeVManager** es una aplicación de escritorio en Python que te permite **administrar, depurar y optimizar** tus listas de reproducción de YouTube desde una interfaz gráfica modular y ligera (Tkinter + YouTube Data API v3).

---

## 📋 Contenido

1. [Características](#características)
2. [Requisitos](#requisitos)
3. [Instalación](#instalación)
4. [Configuración de la API de YouTube](#configuración-de-la-api-de-youtube)
5. [Ejecutar la aplicación](#ejecutar-la-aplicación)
6. [Manual de Usuario Detallado](#manual-de-usuario-detallado)
7. [Estructura de Archivos](#estructura-de-archivos)
8. [Archivos Generados y Logs](#archivos-generados-y-logs)
9. [Seguridad](#seguridad)
10. [Solución de Problemas & FAQ](#solución-de-problemas--faq)
11. [Licencia](#licencia)

---

## Características

* **Filtrado de videos por duración:** elimina intros muy cortas o streams muy largos definiendo rango mínimo y máximo.
* **Eliminación automática/manual:** borra en lote todos los resultados filtrados o selecciona manualmente los que quieras quitar.
* **Visualización de metadatos:** consulta título, duración, vistas, miniatura y enlace al canal desde la app.
* **Gestión masiva de playlists:** carga múltiples playlists, añade y quita en lote.
* **Registro detallado:** cada acción queda en `ytube.log` con timestamp, IDs y resultados.
* **Autenticación OAuth2 segura:** sin exponer claves en el código, usando `client_secrets.json`.
* **Interfaz modular:** cada módulo de funcionalidad está aislado en su propio archivo Tkinter para facilidad de mantenimiento.

---

## Requisitos

* **Python 3.10+**
* **pip** (gestor de paquetes)
* Paquetes en `requirements.txt`
* Cuenta de Google con **YouTube Data API v3** habilitada
* Archivo de credenciales OAuth2 (`client_secrets.json`)

---

## Instalación

```bash
git clone https://github.com/Valentinhp/YOUTUBVMANAGER.git
cd YOUTUBVMANAGER

python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

---

## Configuración de la API de YouTube

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un proyecto y habilita **YouTube Data API v3**
3. En **APIs & Services → Credenciales**, crea un **OAuth Client ID** tipo “Desktop app”
4. Descarga el JSON y renómbralo a `client_secrets.json` en la raíz del proyecto
5. (Primera ejecución) Autoriza en el navegador, copia el código y pégalo en la ventana de la app

### client\_secrets\_template.json (no subir)

```json
{
  "installed": {
    "client_id": "TU_CLIENT_ID.apps.googleusercontent.com",
    "project_id": "tu-proyecto",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "TU_CLIENT_SECRET",
    "redirect_uris": [
      "urn:ietf:wg:oauth:2.0:oob",
      "http://localhost"
    ]
  }
}
```

---

## Ejecutar la aplicación

```bash
python -m src.app
```

---

## Manual de Usuario Detallado

### Autenticación Inicial

1. Al ejecutar sin `token.pickle`, la app abre el navegador.
2. Inicia sesión, acepta permisos y copia el código que te entrega Google.
3. Pégalo en la ventana de la app y presiona **OK**.
4. Se generará `token.pickle` para futuros accesos.

### Filtro de Videos por Duración

1. Selecciona la playlist deseada en el panel izquierdo.
2. Introduce **Duración mínima** y/o **Duración máxima** en formato `hh:mm:ss`.
3. Haz clic en **Filtrar**.
4. La lista mostrará videos **fuera** de ese rango.

> *Tip:* Para detectar intros, usa un valor máximo muy bajo (p.ej. `00:05`). Para streams largos, un mínimo de `01:00:00`.

### Eliminación de Videos

* **Eliminar todos:** borra automáticamente todos los videos filtrados.
* **Eliminar seleccionados:** marca las casillas y luego haz clic en **Eliminar seleccionados**.

> *Precaución:* Verifica antes de confirmar; los eliminados no se pueden recuperar desde la app.

### Visualización de Detalles

1. Haz **doble clic** sobre un video en la lista.
2. Se abre una ventana con:

   * Miniatura
   * Título completo
   * Duración
   * Número de vistas
   * Nombre y enlace del canal

### Gestión de Playlists

* **Añadir playlist:**

  1. Haz clic en **+ Playlist**.
  2. Pega la URL y presiona **Añadir**.
* **Quitar playlist:** selecciona la playlist y haz clic en **Quitar playlist**.

### Revisión de Logs y Auditoría

* **Archivo:** `ytube.log`
* **Formato:**

  ```
  [YYYY-MM-DD HH:MM:SS] ACCIÓN: detalles...
  ```
* **Incluye:** fecha/hora, IDs de video, acción realizada y errores.
* Ábrelo con editor de texto para revisar historial o fallos.

---

## Estructura de Archivos

```
YOUTUBVMANAGER/
├── .gitignore
├── README.md               # Este documento
├── requirements.txt
├── client_secrets.json     # (no subir)
├── token.pickle            # generado tras autenticar
├── ytube.log               # log de actividad
└── src/
    ├── app.py              # Punto de entrada
    ├── auth.py             # OAuth2 y tokens
    ├── config.py           # Constantes y rutas
    ├── yt_manager.py       # Llamadas a YouTube API
    ├── gui/
    │   ├── main_window.py
    │   ├── playlists.py
    │   ├── artist_manager.py
    │   ├── admin_podcasts.py
    │   ├── search_advanced.py
    │   └── top_tracks.py
    └── utils/
        └── spotify_utils.py  # Funciones de soporte y logging
```

---

## Archivos Generados y Logs

* **token.pickle:** token de acceso y refresco.
* **ytube.log:** bitácora de operaciones y errores.

---

## Seguridad

🚫 **Nunca subas**

* `client_secrets.json`
* `token.pickle`

Están incluidos en `.gitignore` para proteger tus credenciales.

---

## Solución de Problemas & FAQ

**P: “invalid\_grant” al autenticar**

* Sincroniza tu reloj local con NTP.
* Borra `token.pickle` y repite autenticación.

**P: La GUI no se abre o falla**

* Asegúrate de instalar todas las dependencias (`pip install -r requirements.txt`).
* Revisa `ytube.log` para errores; busca stacktrace y abre un issue si es necesario.

**P: Cambiar de cuenta de YouTube**

* Borra `token.pickle` y vuelve a iniciar la app; te pedirá autenticar con otra cuenta.

**P: Programar ejecuciones automáticas**

* Usa cron (Linux/macOS) o Task Scheduler (Windows):

  ```bash
  python -m src.app --filter-only --playlist <URL> --min 00:05:00
  ```

---

## Licencia

Proyecto libre para uso educativo y personal.
Desarrollado por [@Valentinhp](https://github.com/Valentinhp)

```
```
