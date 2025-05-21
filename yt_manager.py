import os
import pickle
import time
import logging
import math

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from logger import setup_logging
from utils import iso8601_to_seconds

class YouTubeManager:
    """
    Gestiona autenticación y llamadas a la API de YouTube.
    """
    def __init__(self, token_path: str, scopes: list, log_queue=None):
        # Logger con cola para GUI
        self.logger = setup_logging(log_queue=log_queue)

        self.token_path = token_path
        self.scopes = scopes
        self.youtube = self._authenticate()
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 5  # segundos entre reintentos

    def _authenticate(self):
        """Carga o genera credenciales y devuelve el servicio."""
        creds = None
        secret_file = "client_secrets.json"

        # 1) Si existe token, lo cargo
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'rb') as f:
                    creds = pickle.load(f)
            except Exception as e:
                self.logger.error(f"Error cargando token: {e}")
                creds = None

        # 2) Si no hay creds válidas, refresco o pido login
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("Token refrescado.")
                except Exception as e:
                    self.logger.error(f"No refrescable: {e}")
                    creds = None

            if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(secret_file, self.scopes)
                creds = flow.run_local_server(port=0)
                self.logger.info("Token obtenido por navegador.")

            # Guardo nuevo token
            with open(self.token_path, 'wb') as f:
                pickle.dump(creds, f)
                self.logger.info("Token guardado en disco.")

        # 3) Creo el servicio
        try:
            svc = build('youtube', 'v3', credentials=creds)
            self.logger.info("Servicio YouTube listo.")
            return svc
        except Exception as e:
            self.logger.critical(f"No pudo crear servicio: {e}")
            raise

    def get_channel_details(self, channel_id: str) -> dict:
        """Devuelve título, descripción y suscriptores."""
        try:
            resp = self.youtube.channels().list(
                part="snippet,statistics",
                id=channel_id
            ).execute()
            items = resp.get("items", [])
            if not items:
                self.logger.warning("Canal no encontrado.")
                return {}
            snip = items[0]["snippet"]
            stats = items[0]["statistics"]
            return {
                "title": snip["title"],
                "description": snip["description"],
                "subscriberCount": stats.get("subscriberCount", "N/A")
            }
        except Exception as e:
            self.logger.error(f"Detalle canal falló: {e}")
            return {}

    def search_channels(self, query: str, order: str = "relevance",
                        published_after: str = "", published_before: str = "") -> list:
        """Busca canales según palabras clave y filtros de fecha."""
        try:
            params = {
                "part": "snippet",
                "q": query,
                "type": "channel",
                "order": order,
                "maxResults": 10
            }
            if published_after:
                params["publishedAfter"] = published_after
            if published_before:
                params["publishedBefore"] = published_before

            resp = self.youtube.search().list(**params).execute()
            items = resp.get("items", [])
            results = []
            for it in items:
                kind = it.get("id", {}).get("kind")
                if kind != "youtube#channel":
                    continue
                cid = it["id"].get("channelId")
                if not cid:
                    continue
                sn = it.get("snippet", {})
                results.append({
                    "channelId": cid,
                    "title": sn.get("title", ""),
                    "description": sn.get("description", "")
                })
            self.logger.info(f"Encontrados {len(results)} canales para '{query}'")
            return results
        except HttpError as e:
            content = e.content.decode("utf-8") if hasattr(e, "content") else ""
            if "quotaExceeded" in content:
                self.logger.error("Cuota de API excedida.")
            else:
                self.logger.error(f"Error HTTP en búsqueda: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error en búsqueda: {e}")
            return []

    def get_video_ids_from_channel(self, channel_id: str) -> set:
        """Recupera todos los IDs de video del canal."""
        ids = set()
        try:
            resp = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()
            items = resp.get('items', [])
            if not items:
                self.logger.warning("Canal sin detalles de uploads.")
                return ids
            uploads_pl = items[0]['contentDetails']['relatedPlaylists']['uploads']
            token = None
            while True:
                r = self.youtube.playlistItems().list(
                    part='contentDetails',
                    playlistId=uploads_pl,
                    maxResults=50,
                    pageToken=token
                ).execute()
                for it in r.get('items', []):
                    ids.add(it['contentDetails']['videoId'])
                token = r.get('nextPageToken')
                if not token:
                    break
                time.sleep(1)
            self.logger.info(f"Canal {channel_id} tiene {len(ids)} videos.")
        except Exception as e:
            self.logger.error(f"Error obteniendo videos canal: {e}")
        return ids

    def get_existing_videos_from_playlist(self, playlist_id: str) -> set:
        """IDs de videos ya en la playlist."""
        ids = set()
        try:
            token = None
            while True:
                r = self.youtube.playlistItems().list(
                    part="contentDetails",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=token
                ).execute()
                for it in r.get("items", []):
                    ids.add(it["contentDetails"]["videoId"])
                token = r.get("nextPageToken")
                if not token:
                    break
                time.sleep(1)
            self.logger.info(f"Playlist {playlist_id} tenía {len(ids)} videos.")
        except Exception as e:
            self.logger.error(f"Error leyendo playlist: {e}")
        return ids

    def filter_videos(self, video_ids: set, exclude_keywords: list = [],
                      min_duration=None, max_duration=None) -> set:
        """Filtra según palabras clave y duración (en segundos)."""
        out = set()
        vids = list(video_ids)
        for i in range(0, len(vids), 50):
            chunk = vids[i:i+50]
            try:
                resp = self.youtube.videos().list(
                    part="snippet,contentDetails",
                    id=",".join(chunk)
                ).execute()
                for it in resp.get("items", []):
                    vid = it["id"]
                    title = it["snippet"]["title"]
                    desc = it["snippet"]["description"]
                    dur = iso8601_to_seconds(it["contentDetails"]["duration"])
                    if any(kw.lower() in title.lower() or kw.lower() in desc.lower() for kw in exclude_keywords):
                        continue
                    if min_duration and dur < min_duration:
                        continue
                    if max_duration and dur > max_duration:
                        continue
                    out.add(vid)
            except Exception as e:
                self.logger.error(f"Error filtrando videos: {e}")
        return out

    def add_videos_to_playlist(self, playlist_id: str, video_ids: set,
                               batch_size: int = 20, progress_callback=None,
                               cancel_callback=None):
        """Agrega videos en lotes, con reintentos y callback de progreso."""
        if not video_ids:
            self.logger.info("No hay videos nuevos para agregar.")
            return
        self.logger.info(f"Agregando {len(video_ids)} videos a {playlist_id}")
        vids = list(video_ids)
        total_batches = math.ceil(len(vids) / batch_size)
        added, failed = [], []
        for idx, start in enumerate(range(0, len(vids), batch_size)):
            if cancel_callback and cancel_callback():
                self.logger.info("Operación cancelada.")
                break
            batch = vids[start:start+batch_size]
            for vid in batch:
                if cancel_callback and cancel_callback():
                    break
                for attempt in range(1, self.MAX_RETRIES+1):
                    try:
                        body = {
                            "snippet": {
                                "playlistId": playlist_id,
                                "resourceId": {"kind": "youtube#video", "videoId": vid}
                            }
                        }
                        r = self.youtube.playlistItems().insert(
                            part="snippet", body=body
                        ).execute()
                        if r.get("id"):
                            added.append(vid)
                            self.logger.info(f"Video {vid} agregado.")
                            break
                    except Exception as e:
                        self.logger.error(f"Error agregando {vid} (intento {attempt}): {e}")
                        time.sleep(self.RETRY_DELAY)
            if progress_callback:
                progress_callback(((idx+1)/total_batches)*100)
            time.sleep(15)
        self.logger.info(f"Resumen: total={len(video_ids)}, agregados={len(added)}, fallidos={len(failed)}")

    def process_channel(self, channel_id: str, playlist_id: str, batch_size: int = 20,
                        progress_callback=None, cancel_callback=None, filter_kwargs=None):
        """Flujo: tomar videos de canal, filtrar, comparar con playlist y agregar."""
        self.logger.info(f"Procesando canal {channel_id} → {playlist_id}")
        vids = self.get_video_ids_from_channel(channel_id)
        if not vids:
            self.logger.info("No hay videos en el canal.")
            return
        if filter_kwargs:
            vids = self.filter_videos(
                vids,
                exclude_keywords=filter_kwargs.get("exclude_keywords", []),
                min_duration=filter_kwargs.get("min_duration"),
                max_duration=filter_kwargs.get("max_duration")
            )
        existing = self.get_existing_videos_from_playlist(playlist_id)
        to_add = vids - existing
        self.logger.info(f"Videos nuevos a agregar: {len(to_add)}")
        self.add_videos_to_playlist(playlist_id, to_add, batch_size, progress_callback, cancel_callback)

    def create_playlist(self, title: str, description: str, privacy: str = "private") -> str:
        """Crea una playlist y retorna su ID."""
        try:
            body = {
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": privacy}
            }
            r = self.youtube.playlists().insert(part="snippet,status", body=body).execute() 
            pid = r.get("id", "")
            self.logger.info(f"Playlist creada: {pid}")
            return pid
        except Exception as e:
            self.logger.error(f"Error creando playlist: {e}")
            return ""

    def empty_playlist(self, playlist_id: str):
        """Borra todos los videos de una playlist."""
        try:
            token = None
            while True:
                r = self.youtube.playlistItems().list(
                    part="id", playlistId=playlist_id,
                    maxResults=50, pageToken=token
                ).execute()
                items = r.get("items", [])
                if not items:
                    break
                for it in items:
                    pid = it["id"]
                    try:
                        self.youtube.playlistItems().delete(id=pid).execute()
                        self.logger.info(f"Eliminado {pid}")
                    except Exception as ex:
                        self.logger.error(f"Error al eliminar {pid}: {ex}")
                token = r.get("nextPageToken")
                if not token:
                    break
            self.logger.info("Playlist vaciada.")
        except Exception as e:
            self.logger.error(f"Error vaciando playlist: {e}")

    def list_playlists(self) -> list:
        """Devuelve lista de tus playlists con título, descripción y privacidad."""
        try:
            r = self.youtube.playlists().list(
                part="snippet,status", mine=True, maxResults=50
            ).execute()
            items = r.get("items", [])
            out = []
            for it in items:
                out.append({
                    "playlistId": it["id"],
                    "title": it["snippet"]["title"],
                    "description": it["snippet"]["description"],
                    "privacyStatus": it["status"]["privacyStatus"]
                })
            self.logger.info(f"Tienes {len(out)} playlists.")
            return out
        except Exception as e:
            self.logger.error(f"Error listando playlists: {e}")
            return []

    def update_playlist(self, playlist_id: str, title: str, description: str, privacy: str):
        """Actualiza título/desc/privacidad de una playlist."""
        try:
            body = {
                "id": playlist_id,
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": privacy}
            }
            r = self.youtube.playlists().update(part="snippet,status", body=body).execute()
            self.logger.info(f"Playlist {playlist_id} actualizada.")
            return r
        except Exception as e:
            self.logger.error(f"Error actualizando playlist: {e}")
            return None

    def delete_playlist(self, playlist_id: str):
        """Elimina una playlist (solo con OAuth adecuado)."""
        try:
            self.youtube.playlists().delete(id=playlist_id).execute()
            self.logger.info(f"Playlist {playlist_id} eliminada.")
        except Exception as e:
            self.logger.error(f"Error eliminando playlist: {e}")

    def remove_videos_by_duration(self, playlist_id: str, min_duration: int = None, max_duration: int = None) -> int:
        """
        Elimina de la playlist videos cuya duración (en segundos) esté
        dentro del rango dado. Devuelve cuántos eliminó.
        """
        # Recojo {videoId: itemId}
        mapping = {}
        token = None
        while True:
            r = self.youtube.playlistItems().list(
                part="id,contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=token
            ).execute()
            for it in r.get("items", []):
                vid = it["contentDetails"]["videoId"]
                mapping[vid] = it["id"]
            token = r.get("nextPageToken")
            if not token:
                break

        vids = list(mapping.keys())
        removed = 0
        for i in range(0, len(vids), 50):
            chunk = vids[i:i+50]
            try:
                r = self.youtube.videos().list(
                    part="contentDetails", id=",".join(chunk)
                ).execute()
                for it in r.get("items", []):
                    vid = it["id"]
                    dur = iso8601_to_seconds(it["contentDetails"]["duration"])
                    if min_duration and dur < min_duration:
                        continue
                    if max_duration and dur > max_duration:
                        continue
                    item_id = mapping.get(vid)
                    if item_id:
                        self.youtube.playlistItems().delete(id=item_id).execute()
                        removed += 1
                        self.logger.info(f"Eliminado video {vid}.")
            except Exception as e:
                self.logger.error(f"Error eliminando por duración: {e}")
        return removed

    def get_trending_videos(self, regionCode='US', maxResults=10) -> list:
        """Devuelve los videos más populares en la región dada."""
        try:
            r = self.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                chart="mostPopular",
                regionCode=regionCode,
                maxResults=maxResults
            ).execute()
            return r.get("items", [])
        except Exception as e:
            self.logger.error(f"Error trending: {e}")
            return []

    @classmethod
    def update_token_pickle(cls, token_path: str, client_secrets_file: str, scopes: list):
        """Forzar actualización manual del token."""
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes)
        creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as f:
            pickle.dump(creds, f)
        logging.getLogger('YouTubeManager').info("Token actualizado manualmente.")
