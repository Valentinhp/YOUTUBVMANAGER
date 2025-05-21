# 🎬 YouTubeVManager

Aplicación de escritorio en Python para administrar y depurar listas de reproducción de YouTube desde una GUI modular y ligera.

---

## 🚀 Funcionalidades

- **Filtrar videos por duración** (p.ej. eliminar intros largos o streams extensos)  
- **Eliminar videos** (automático o manual) directamente de una playlist  
- **Ver detalles de canal y metadatos** de cada video (título, vistas, duración)  
- **Cargar y gestionar múltiples playlists** en lote  
- **Registro de actividad** en `ytube.log` para debugging y auditoría  
- **Autenticación segura OAuth2** con la API de YouTube v3  
- **Interfaz gráfica** desarrollada con Tkinter, en módulos independientes  

---

## ⚙️ Requisitos

- **Python 3.10+**  
- Paquetes listados en `requirements.txt`  
- **YouTube Data API v3** habilitada  
- Credenciales OAuth2 (archivo `client_secrets.json`)

---

## 📦 Instalación

```bash
git clone https://github.com/Valentinhp/YOUTUBVMANAGER.git
cd YOUTUBVMANAGER

# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
