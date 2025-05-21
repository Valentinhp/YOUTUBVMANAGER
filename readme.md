# 🎬 YouTubeVManager

Aplicación de escritorio en Python para administrar y depurar listas de reproducción de YouTube de forma visual y automática.

Te permite filtrar videos por duración, eliminar los que no te sirven, ver detalles del canal, y llevar un control completo desde una GUI simple.

---

## 🚀 Funciones principales

✅ Filtro de videos por duración  
✅ Eliminación automática o manual de videos  
✅ Detalles de canal y videos visibles desde la interfaz  
✅ Logs de actividad guardados en `ytube.log`  
✅ Interfaz hecha con Tkinter  
✅ Integración con la API de YouTube vía `googleapiclient`

---

## ⚙️ Requisitos

- Python 3.10+
- Acceso a la API de YouTube (con tu propia `client_secrets.json`)
- Tener Spotipy y Google API Client instalados

---

## 📦 Instalación rápida

```bash
git clone https://github.com/Valentinhp/YOUTUBVMANAGER.git
cd YOUTUBVMANAGER
python -m venv .venv
.venv\Scripts\activate      # En Windows
# source .venv/bin/activate # En Linux/Mac
pip install -r requirements.txt
