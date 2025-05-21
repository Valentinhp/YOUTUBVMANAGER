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

- **Filtrado de videos por duración**: elimina intros muy cortas o streams muy largos definiendo rango mínimo y máximo.  
- **Eliminación automática/manual**: borra en lote todos los resultados filtrados o selecciona manualmente los que quieras quitar.  
- **Visualización de metadatos**: consulta título, duración, vistas, miniatura y enlace al canal desde la app.  
- **Gestión masiva de playlists**: carga múltiples playlists, añade y quita en lote.  
- **Registro detallado**: cada acción queda en `ytube.log` con timestamp, IDs y resultados.  
- **Autenticación OAuth2 segura**: sin exponer claves en el código, usando `client_secrets.json`.  
- **Interfaz modular**: cada módulo de funcionalidad está aislado en su propio archivo Tkinter para facilidad de mantenimiento.

---

## Requisitos

- **Python 3.10+**  
- **pip** (gestor de paquetes)  
- Paquetes en `requirements.txt`  
- Cuenta de Google con **YouTube Data API v3** habilitada  
- Archivo de credenciales OAuth2 (`client_secrets.json`)  

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
