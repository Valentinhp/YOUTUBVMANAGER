"""
app.py – Gestor de playlists y canales de YouTube
Versión: 22-may-2025

Mejoras añadidas respecto al original:

1. **Duraciones coherentes**: el usuario siempre escribe/ve minutos; el
   programa sigue trabajando en segundos internamente.
2. **Ayuda dentro de la interfaz**:
   • Ventana “Configuración” → mini-tip con ejemplo de duración.
   • Ventana “Eliminar Videos por Duración” → bloque “¿Cómo funciona?”
     con ejemplos paso a paso.
3. **Barra de estado** menciona el filtro de duración activo.
4. Comentarios claros y directos a lo largo del código.

No se eliminó ni se cambió ninguna funcionalidad existente.
"""

import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

from logger import setup_logging
from yt_manager import YouTubeManager


class App:
    """Interfaz Tkinter y puente hacia YouTubeManager."""

    # ------------------------------------------------------------------ #
    # 1. CONSTRUCTOR Y VARIABLES GLOBALES
    # ------------------------------------------------------------------ #
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.geometry("900x700")
        root.title("YouTube Playlist Manager")

        # ---- cola de logs + logger ------------------------------------
        self.log_queue = queue.Queue()
        self.logger = setup_logging(log_queue=self.log_queue)

        # ---- configuración por defecto (duraciones en segundos) -------
        self.config = {
            "retry_delay": 5,            # seg
            "batch_size": 20,
            "filter_exclude_keywords": "",
            "filter_min_duration": 0,    # seg (0 = sin mínimo)
            "filter_max_duration": 0,    # seg (0 = sin máximo)
            "auto_update_interval": 0    # min
        }
        self.cancel_operation = False

        # ---- variables Tkinter (para widgets) -------------------------
        self.token_file      = tk.StringVar(value="token.pickle")
        self.search_query    = tk.StringVar()
        self.channel_id      = tk.StringVar()
        self.playlist_id     = tk.StringVar()
        self.order_option    = tk.StringVar(value="relevance")
        self.published_after = tk.StringVar()
        self.published_before= tk.StringVar()
        self.status_var      = tk.StringVar(value="Listo")
        self.progress_value  = tk.DoubleVar(value=0)

        # ---- contenedores --------------------------------------------
        self.batch_channels: list[dict] = []
        self.playlist_data : list[dict] = []

        # ---- construir UI + lector de logs ---------------------------
        self.build_ui()
        self.update_log()

        if self.config["auto_update_interval"] > 0:
            self.start_auto_update()

    # ------------------------------------------------------------------ #
    # 2. INTERFAZ COMPLETA
    # ------------------------------------------------------------------ #
    def build_ui(self):
        """Crea menús, pestañas y widgets."""
        # ===== MENÚ SUPERIOR ==========================================
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        archivo = tk.Menu(menubar, tearoff=0)
        archivo.add_command(label="Ver Historial", command=self.view_log_history)
        archivo.add_command(label="Exportar Log", command=self.export_log)
        menubar.add_cascade(label="Archivo", menu=archivo)

        cfg = tk.Menu(menubar, tearoff=0)
        cfg.add_command(label="Configuración", command=self.open_config_window)
        cfg.add_command(label="Actualizar Token", command=self.update_token_action)
        menubar.add_cascade(label="Configuración", menu=cfg)

        ayuda = tk.Menu(menubar, tearoff=0)
        ayuda.add_command(label="Ayuda", command=self.open_help_window)
        ayuda.add_command(label="Compartir Resultados", command=self.share_results)
        menubar.add_cascade(label="Ayuda", menu=ayuda)

        # ===== NOTEBOOK PRINCIPAL =====================================
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # ---------------- PESTAÑA 1: Búsqueda y Canal -----------------
        f1 = ttk.Frame(notebook, padding=10)
        f1.grid_rowconfigure(5, weight=1)
        f1.grid_rowconfigure(6, weight=1)
        f1.grid_columnconfigure(1, weight=1)
        notebook.add(f1, text="Búsqueda y Canal")

        # Token + búsqueda
        ttk.Label(f1, text="Archivo token.pickle:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(f1, textvariable=self.token_file, width=40, state="readonly")\
            .grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(f1, text="Buscar canales:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(f1, textvariable=self.search_query, width=40)\
            .grid(row=1, column=1, sticky="ew", pady=2)
        self.btn_search = ttk.Button(f1, text="Buscar", command=self.do_search)
        self.btn_search.grid(row=1, column=2, sticky="ew", padx=5, pady=2)

        # Filtros de búsqueda
        ttk.Label(f1, text="Ordenar por:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Combobox(
            f1, textvariable=self.order_option,
            values=["relevance", "date", "viewCount", "rating"],
            state="readonly", width=37
        ).grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(f1, text="Publicado después (ISO):").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(f1, textvariable=self.published_after, width=40)\
            .grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Label(f1, text="Publicado antes (ISO):").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Entry(f1, textvariable=self.published_before, width=40)\
            .grid(row=4, column=1, sticky="ew", pady=2)

        # Resultados de búsqueda
        rf = ttk.Frame(f1)
        rf.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        rf.grid_rowconfigure(0, weight=1)
        rf.grid_columnconfigure(0, weight=1)
        self.tree_results = ttk.Treeview(rf, columns=("titulo", "channelId"), show="headings")
        self.tree_results.heading("titulo", text="Título")
        self.tree_results.heading("channelId", text="Channel ID")
        self.tree_results.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(rf, orient="vertical", command=self.tree_results.yview)
        self.tree_results.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree_results.bind("<<TreeviewSelect>>", self.on_result_select)

        # Detalles del canal
        self.details_text = scrolledtext.ScrolledText(f1, wrap="word", width=40, height=6)
        self.details_text.grid(row=6, column=0, columnspan=3,
                               sticky="nsew", padx=5, pady=5)

        # Botones de acción
        ttk.Button(f1, text="Agregar Canal a Batch",
                   command=self.add_channel_to_batch)\
            .grid(row=7, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        ttk.Label(f1, text="Channel ID:").grid(row=8, column=0, sticky="e", pady=2)
        ttk.Entry(f1, textvariable=self.channel_id, width=40)\
            .grid(row=8, column=1, sticky="ew", pady=2)
        ttk.Label(f1, text="Playlist ID:").grid(row=9, column=0, sticky="e", pady=2)
        ttk.Entry(f1, textvariable=self.playlist_id, width=40)\
            .grid(row=9, column=1, sticky="ew", pady=2)
        ttk.Button(f1, text="Procesar Canal",
                   command=self.process_channel_action)\
            .grid(row=9, column=2, sticky="ew", padx=5, pady=2)
        ttk.Button(f1, text="Ver Videos de Playlist",
                   command=self.view_playlist_videos)\
            .grid(row=10, column=0, columnspan=3, sticky="ew", padx=5, pady=2)
        ttk.Button(f1, text="Recomendaciones",
                   command=self.recommendations_action)\
            .grid(row=11, column=0, columnspan=3, sticky="ew", padx=5, pady=2)

        # Barra de estado y progreso
        ttk.Label(f1, text="Estado:").grid(row=12, column=0, sticky="w", pady=2)
        ttk.Label(f1, textvariable=self.status_var)\
            .grid(row=12, column=1, sticky="w", pady=2)
        self.progress_bar = ttk.Progressbar(
            f1, orient="horizontal", mode="determinate",
            variable=self.progress_value, maximum=100
        )
        self.progress_bar.grid(row=12, column=2, sticky="ew", padx=5, pady=2)

        # ---------------- PESTAÑA 2: Batch Processing ------------------
        fb = ttk.Frame(notebook, padding=10)
        fb.grid_rowconfigure(1, weight=1)
        fb.grid_columnconfigure(0, weight=1)
        notebook.add(fb, text="Batch Processing")

        ttk.Label(fb, text="Canales a procesar:")\
            .grid(row=0, column=0, sticky="w", pady=2)
        bb = ttk.Frame(fb)
        bb.grid(row=1, column=0, columnspan=3,
                sticky="nsew", padx=5, pady=5)
        bb.grid_rowconfigure(0, weight=1)
        bb.grid_columnconfigure(0, weight=1)
        sb2 = ttk.Scrollbar(bb, orient="vertical")
        self.batch_listbox = tk.Listbox(bb, yscrollcommand=sb2.set)
        self.batch_listbox.grid(row=0, column=0, sticky="nsew")
        sb2.config(command=self.batch_listbox.yview)
        sb2.grid(row=0, column=1, sticky="ns")
        ttk.Button(fb, text="Eliminar Canal de Batch",
                   command=self.remove_channel_from_batch)\
            .grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        ttk.Button(fb, text="Procesar Todos",
                   command=self.process_batch_action)\
            .grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(fb, text="Cancelar",
                   command=self.cancel_current_operation)\
            .grid(row=2, column=2, sticky="ew", padx=5, pady=5)

        # ---------------- PESTAÑA 3: Playlists -------------------------
        fp = ttk.Frame(notebook, padding=10)
        fp.grid_rowconfigure(1, weight=1)
        fp.grid_columnconfigure(0, weight=1)
        notebook.add(fp, text="Playlists")

        ttk.Label(fp, text="Tus Playlists:")\
            .grid(row=0, column=0, sticky="w", pady=2)
        plf = ttk.Frame(fp)
        plf.grid(row=1, column=0, columnspan=4,
                 sticky="nsew", padx=5, pady=5)
        plf.grid_rowconfigure(0, weight=1)
        plf.grid_columnconfigure(0, weight=1)
        sb3 = ttk.Scrollbar(plf, orient="vertical")
        self.playlist_listbox = tk.Listbox(plf, yscrollcommand=sb3.set)
        self.playlist_listbox.grid(row=0, column=0, sticky="nsew")
        sb3.config(command=self.playlist_listbox.yview)
        sb3.grid(row=0, column=1, sticky="ns")
        self.playlist_listbox.bind("<<ListboxSelect>>",
                                   self.on_select_playlist)

        ttk.Button(fp, text="Refrescar",
                   command=self.refresh_playlists)\
            .grid(row=2, column=0, sticky="ew", padx=5, pady=2)
        ttk.Button(fp, text="Crear Nueva",
                   command=self.create_playlist_action)\
            .grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(fp, text="Actualizar",
                   command=self.update_playlist_action)\
            .grid(row=2, column=2, sticky="ew", padx=5, pady=2)
        ttk.Button(fp, text="Borrar",
                   command=self.delete_playlist_action)\
            .grid(row=2, column=3, sticky="ew", padx=5, pady=2)
        ttk.Button(fp, text="Vaciar",
                   command=self.empty_playlist_action)\
            .grid(row=3, column=0, columnspan=4,
                  sticky="ew", padx=5, pady=5)
        ttk.Button(fp, text="Eliminar Videos por Duración",
                   command=self.remove_videos_by_duration_action)\
            .grid(row=4, column=0, columnspan=4,
                  sticky="ew", padx=5, pady=5)

        # ===== ÁREA DE LOG ============================================
        lf = ttk.Frame(self.root, padding=5)
        lf.grid(row=1, column=0, sticky="nsew")
        self.root.rowconfigure(1, weight=1)
        lf.grid_rowconfigure(0, weight=1)
        lf.grid_columnconfigure(0, weight=1)
        self.log_text = tk.Text(lf, state='disabled', wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        sb4 = ttk.Scrollbar(lf, orient="vertical",
                            command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb4.set)
        sb4.grid(row=0, column=1, sticky="ns")

    # ------------------------------------------------------------------ #
    # 3. REGISTRO / ESTADO / PROGRESO
    # ------------------------------------------------------------------ #
    def update_log(self):
        """Vacía la cola y escribe los logs en pantalla cada 100 ms."""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.config(state='normal')
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.update_log)

    def update_status(self, text: str):
        self.root.after(0, lambda: self.status_var.set(text))

    def update_progress(self, value: float):
        self.root.after(0, lambda: self.progress_value.set(value))

    # ------------------------------------------------------------------ #
    # 4. BÚSQUEDA DE CANALES
    # ------------------------------------------------------------------ #
    def on_result_select(self, event):
        item = self.tree_results.focus()
        if not item:
            return
        vals = self.tree_results.item(item, "values")
        if len(vals) < 2:
            return
        cid = vals[1]
        self.channel_id.set(cid)

        def worker():
            mgr = YouTubeManager(
                self.token_file.get(),
                ["https://www.googleapis.com/auth/youtube.force-ssl"],
                log_queue=self.log_queue
            )
            details = mgr.get_channel_details(cid)
            self.root.after(0,
                            lambda: self._show_channel_details(details))

        threading.Thread(target=worker, daemon=True).start()

    def _show_channel_details(self, details: dict | None):
        self.details_text.config(state='normal')
        self.details_text.delete("1.0", tk.END)
        if details:
            self.details_text.insert(tk.END,
                                     f"Título: {details.get('title')}\n")
            self.details_text.insert(tk.END,
                                     f"Descripción: "
                                     f"{details.get('description')}\n")
            self.details_text.insert(tk.END,
                                     f"Suscriptores: "
                                     f"{details.get('subscriberCount')}\n")
        else:
            self.details_text.insert(tk.END,
                                     "No hay detalles para este canal.\n")
        self.details_text.config(state='disabled')

    def do_search(self):
        query = self.search_query.get().strip()
        if not query:
            messagebox.showwarning("Atención", "Escribe algo para buscar.")
            return

        for iid in self.tree_results.get_children():
            self.tree_results.delete(iid)
        self.details_text.config(state='normal')
        self.details_text.delete("1.0", tk.END)
        self.details_text.config(state='disabled')
        self.update_status("Buscando canales...")
        self.btn_search.config(state='disabled')

        def worker():
            mgr = YouTubeManager(
                self.token_file.get(),
                ["https://www.googleapis.com/auth/youtube.force-ssl"],
                log_queue=self.log_queue
            )
            channels = mgr.search_channels(
                query,
                self.order_option.get(),
                self.published_after.get(),
                self.published_before.get()
            )
            self.root.after(0,
                            lambda: self._insert_search_results(channels))

        threading.Thread(target=worker, daemon=True).start()

    def _insert_search_results(self, channels: list[dict]):
        for ch in channels:
            self.tree_results.insert("",
                                     tk.END,
                                     values=(ch["title"],
                                             ch["channelId"]))
        self.update_status("Búsqueda finalizada.")
        self.btn_search.config(state='normal')

    # ------------------------------------------------------------------ #
    # 5. BATCH LISTA (add / remove)
    # ------------------------------------------------------------------ #
    def add_channel_to_batch(self):
        cid = self.channel_id.get().strip()
        if not cid:
            messagebox.showwarning("Atención",
                                   "Selecciona un canal primero.")
            return
        for ch in self.batch_channels:
            if ch["channelId"] == cid:
                messagebox.showinfo("Información",
                                    "El canal ya está en la lista.")
                return

        title = cid
        lines = self.details_text.get("1.0", tk.END).splitlines()
        if lines and lines[0].startswith("Título:"):
            title = lines[0].split(":", 1)[1].strip()
        self.batch_channels.append({"channelId": cid, "title": title})
        self.batch_listbox.insert(tk.END, f"{title} (ID: {cid})")
        self.logger.info(f"Canal {cid} agregado a batch.")

    def remove_channel_from_batch(self):
        sel = self.batch_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        removed = self.batch_channels.pop(idx)
        self.batch_listbox.delete(idx)
        self.logger.info(f"Canal {removed['channelId']} removido de batch.")

    # ------------------------------------------------------------------ #
    # 6. PROCESAR CANAL INDIVIDUAL
    # ------------------------------------------------------------------ #
    def process_channel_action(self):
        channel = self.channel_id.get().strip()
        playlist = self.playlist_id.get().strip()
        token = self.token_file.get().strip()
        if not channel or not playlist or not token:
            messagebox.showwarning("Atención",
                                   "Faltan datos (Channel, Playlist o Token).")
            return

        min_min = self.config["filter_min_duration"] // 60
        max_min = self.config["filter_max_duration"] // 60
        dur_msg = (f" | Filtro {min_min or 0}-{max_min or '∞'} min"
                   if (min_min or max_min) else "")
        self.update_status(f"Procesando canal...{dur_msg}")
        self.update_progress(0)
        self.btn_search.config(state='disabled')
        self.cancel_operation = False

        exclude = [kw.strip() for kw in
                   self.config["filter_exclude_keywords"].split(",")
                   if kw.strip()]
        filter_kwargs = {
            "exclude_keywords": exclude,
            "min_duration": self.config["filter_min_duration"] or None,
            "max_duration": self.config["filter_max_duration"] or None
        }

        def worker():
            try:
                mgr = YouTubeManager(
                    token,
                    ["https://www.googleapis.com/auth/youtube.force-ssl"],
                    log_queue=self.log_queue
                )
                mgr.RETRY_DELAY = self.config["retry_delay"]
                mgr.process_channel(
                    channel, playlist, self.config["batch_size"],
                    progress_callback=self.update_progress,
                    cancel_callback=lambda: self.cancel_operation,
                    filter_kwargs=filter_kwargs
                )
                self.logger.info(f"Proceso del canal {channel} finalizado.")
                self.update_status("Proceso completado.")
            except Exception as e:
                self.logger.critical(f"Error procesando canal {channel}: {e}")
                self.update_status("Error en el proceso.")
            finally:
                self.root.after(
                    0, lambda: self.btn_search.config(state='normal'))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    # 7. PROCESAR BATCH
    # ------------------------------------------------------------------ #
    def process_batch_action(self):
        playlist = self.playlist_id.get().strip()
        token = self.token_file.get().strip()
        if not playlist or not token:
            messagebox.showwarning("Atención",
                                   "Faltan datos (Playlist o Token).")
            return
        if not self.batch_channels:
            messagebox.showwarning("Atención",
                                   "No hay canales en la lista de batch.")
            return

        min_min = self.config["filter_min_duration"] // 60
        max_min = self.config["filter_max_duration"] // 60
        dur_msg = (f" | Filtro {min_min or 0}-{max_min or '∞'} min"
                   if (min_min or max_min) else "")
        self.update_status(f"Procesando batch de canales...{dur_msg}")
        self.update_progress(0)
        self.cancel_operation = False
        total = len(self.batch_channels)

        def worker():
            try:
                for idx, ch in enumerate(self.batch_channels):
                    if self.cancel_operation:
                        self.logger.info("Operación batch cancelada.")
                        break
                    self.logger.info(f"Procesando canal {ch['channelId']} "
                                     f"({idx + 1}/{total})")
                    mgr = YouTubeManager(
                        token,
                        ["https://www.googleapis.com/auth/youtube.force-ssl"],
                        log_queue=self.log_queue
                    )
                    mgr.RETRY_DELAY = self.config["retry_delay"]
                    fk = {
                        "exclude_keywords": [kw.strip() for kw in
                                             self.config["filter_exclude_keywords"]
                                             .split(",") if kw.strip()],
                        "min_duration": self.config["filter_min_duration"] or None,
                        "max_duration": self.config["filter_max_duration"] or None
                    }
                    mgr.process_channel(
                        ch["channelId"], playlist, self.config["batch_size"],
                        progress_callback=self.update_progress,
                        cancel_callback=lambda: self.cancel_operation,
                        filter_kwargs=fk
                    )
                    time.sleep(2)
                self.update_status("Batch completado.")
            except Exception as e:
                self.logger.error(f"Error en batch: {e}")
                self.update_status("Error en batch.")

        threading.Thread(target=worker, daemon=True).start()

    def cancel_current_operation(self):
        self.cancel_operation = True
        self.update_status("Cancelando operación...")

    # ------------------------------------------------------------------ #
    # 8. PLAYLISTS – VER, CRUD, LIMPIAR
    # ------------------------------------------------------------------ #
    def view_playlist_videos(self):
        pid = self.playlist_id.get().strip()
        if not pid:
            messagebox.showwarning("Atención",
                                   "Ingresa el ID de la playlist.")
            return

        def fetch():
            mgr = YouTubeManager(
                self.token_file.get(),
                ["https://www.googleapis.com/auth/youtube.force-ssl"],
                log_queue=self.log_queue
            )
            vids = mgr.get_existing_videos_from_playlist(pid)
            self.root.after(0, lambda:
                            self._show_videos_window(list(vids)))

        threading.Thread(target=fetch, daemon=True).start()

    def _show_videos_window(self, videos: list[str]):
        win = tk.Toplevel(self.root)
        win.title("Videos de la Playlist")
        win.geometry("400x300")
        frame = ttk.Frame(win, padding=5)
        frame.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical")
        lb = tk.Listbox(frame, yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.config(command=lb.yview)
        sb.pack(side="right", fill="y")
        for v in videos:
            lb.insert(tk.END, v)
        ttk.Button(win, text="Cerrar",
                   command=win.destroy).pack(pady=5)

    def refresh_playlists(self):
        def worker():
            mgr = YouTubeManager(
                self.token_file.get(),
                ["https://www.googleapis.com/auth/youtube.force-ssl"],
                log_queue=self.log_queue
            )
            pls = mgr.list_playlists()
            self.root.after(0, lambda:
                            self._insert_playlists(pls))

        threading.Thread(target=worker, daemon=True).start()

    def _insert_playlists(self, playlists: list[dict]):
        self.playlist_listbox.delete(0, tk.END)
        self.playlist_data = playlists
        for pl in playlists:
            self.playlist_listbox.insert(
                tk.END, f"{pl['title']} (ID: {pl['playlistId']})")

    def on_select_playlist(self, event):
        sel = self.playlist_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        pl = self.playlist_data[idx]
        self.playlist_id.set(pl["playlistId"])

    # ------------------ CREAR PLAYLIST -------------------------------
    def create_playlist_action(self):
        win = tk.Toplevel(self.root)
        win.title("Crear Playlist")

        ttk.Label(win, text="Título:")\
            .grid(row=0, column=0, padx=5, pady=5, sticky="w")
        title_var = tk.StringVar()
        ttk.Entry(win, textvariable=title_var, width=40)\
            .grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(win, text="Descripción:")\
            .grid(row=1, column=0, padx=5, pady=5, sticky="w")
        desc_var = tk.StringVar()
        ttk.Entry(win, textvariable=desc_var, width=40)\
            .grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(win, text="Privacidad:")\
            .grid(row=2, column=0, padx=5, pady=5, sticky="w")
        priv_var = tk.StringVar(value="private")
        ttk.Combobox(win, textvariable=priv_var,
                     values=["private", "unlisted", "public"],
                     state="readonly", width=37)\
            .grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        def create():
            t = title_var.get().strip()
            d = desc_var.get().strip()
            p = priv_var.get().strip()
            if not t:
                messagebox.showwarning("Falta título",
                                       "Ponle un título a la playlist.")
                return

            def worker():
                mgr = YouTubeManager(
                    self.token_file.get(),
                    ["https://www.googleapis.com/auth/youtube.force-ssl"],
                    log_queue=self.log_queue
                )
                pid = mgr.create_playlist(t, d, p)
                if pid:
                    self.playlist_id.set(pid)
                    messagebox.showinfo("Éxito",
                                        f"Playlist creada: {pid}")
                    self.refresh_playlists()
                    win.destroy()
                else:
                    messagebox.showerror("Error",
                                         "No se pudo crear la playlist.")

            threading.Thread(target=worker, daemon=True).start()

        ttk.Button(win, text="Crear Playlist",
                   command=create)\
            .grid(row=3, column=0, columnspan=2, pady=10)
        win.grid_columnconfigure(0, weight=1)
        win.grid_columnconfigure(1, weight=1)

    # ----------------- ACTUALIZAR PLAYLIST ----------------------------
    def update_playlist_action(self):
        pid = self.playlist_id.get().strip()
        if not pid:
            messagebox.showwarning("Atención",
                                   "Selecciona o ingresa el ID de una playlist.")
            return

        win = tk.Toplevel(self.root)
        win.title("Actualizar Playlist")

        ttk.Label(win, text="Nuevo Título:")\
            .grid(row=0, column=0, padx=5, pady=5, sticky="w")
        title_var = tk.StringVar()
        ttk.Entry(win, textvariable=title_var, width=40)\
            .grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(win, text="Nueva Descripción:")\
            .grid(row=1, column=0, padx=5, pady=5, sticky="w")
        desc_var = tk.StringVar()
        ttk.Entry(win, textvariable=desc_var, width=40)\
            .grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(win, text="Nueva Privacidad:")\
            .grid(row=2, column=0, padx=5, pady=5, sticky="w")
        priv_var = tk.StringVar(value="private")
        ttk.Combobox(win, textvariable=priv_var,
                     values=["private", "unlisted", "public"],
                     state="readonly", width=37)\
            .grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        def update():
            t = title_var.get().strip()
            d = desc_var.get().strip()
            p = priv_var.get().strip()
            if not t:
                messagebox.showwarning("Falta título",
                                       "El título es obligatorio.")
                return

            def worker():
                mgr = YouTubeManager(
                    self.token_file.get(),
                    ["https://www.googleapis.com/auth/youtube.force-ssl"],
                    log_queue=self.log_queue
                )
                resp = mgr.update_playlist(pid, t, d, p)
                if resp:
                    messagebox.showinfo("Éxito",
                                        f"Playlist {pid} actualizada.")
                    self.refresh_playlists()
                    win.destroy()
                else:
                    messagebox.showerror("Error",
                                         "No se pudo actualizar la playlist.")

            threading.Thread(target=worker, daemon=True).start()

        ttk.Button(win, text="Actualizar Playlist",
                   command=update)\
            .grid(row=3, column=0, columnspan=2, pady=10)
        win.grid_columnconfigure(0, weight=1)
        win.grid_columnconfigure(1, weight=1)

    # ------------------ BORRAR PLAYLIST -------------------------------
    def delete_playlist_action(self):
        pid = self.playlist_id.get().strip()
        if not pid:
            messagebox.showwarning("Atención",
                                   "Selecciona o ingresa el ID de una playlist.")
            return
        if not messagebox.askyesno("Confirmar",
                                   "¿Estás seguro de eliminar esta playlist?"):
            return

        def worker():
            mgr = YouTubeManager(
                self.token_file.get(),
                ["https://www.googleapis.com/auth/youtube.force-ssl"],
                log_queue=self.log_queue
            )
            mgr.delete_playlist(pid)
            messagebox.showinfo("Éxito", f"Playlist {pid} eliminada.")
            self.playlist_id.set("")
            self.refresh_playlists()

        threading.Thread(target=worker, daemon=True).start()

    # ------------------ VACIAR PLAYLIST -------------------------------
    def empty_playlist_action(self):
        pid = self.playlist_id.get().strip()
        if not pid:
            messagebox.showwarning("Atención",
                                   "Selecciona o ingresa el ID de una playlist.")
            return
        if not messagebox.askyesno("Confirmar",
                                   "¿Deseas vaciar la playlist "
                                   "(eliminar todos sus videos)?"):
            return

        def worker():
            mgr = YouTubeManager(
                self.token_file.get(),
                ["https://www.googleapis.com/auth/youtube.force-ssl"],
                log_queue=self.log_queue
            )
            mgr.empty_playlist(pid)
            messagebox.showinfo("Éxito", f"Playlist {pid} vaciada.")

        threading.Thread(target=worker, daemon=True).start()

    # ------ ELIMINAR VIDEOS POR DURACIÓN (con ayuda integrada) -------
    def remove_videos_by_duration_action(self):
        win = tk.Toplevel(self.root)
        win.title("Eliminar Videos por Duración")

        ttk.Label(win, text="Playlist ID:")\
            .grid(row=0, column=0, padx=5, pady=5, sticky="w")
        pid_var = tk.StringVar(value=self.playlist_id.get())
        ttk.Entry(win, textvariable=pid_var, width=40)\
            .grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(win, text="Duración mínima (min):")\
            .grid(row=1, column=0, padx=5, pady=5, sticky="w")
        min_var = tk.StringVar()
        ttk.Entry(win, textvariable=min_var, width=20)\
            .grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(win, text="Duración máxima (min):")\
            .grid(row=2, column=0, padx=5, pady=5, sticky="w")
        max_var = tk.StringVar()
        ttk.Entry(win, textvariable=max_var, width=20)\
            .grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        # Bloque de ayuda contextual
        help_txt = (
            "¿Cómo funciona?\n"
            "Se eliminarán de la playlist todos los vídeos cuya duración\n"
            "esté FUERA del rango especificado.\n\n"
            "Ejemplos:\n"
            "  • Min=1  | Max=20  → solo quedan vídeos de 1-20 min.\n"
            "  • Min=   | Max=3   → elimina los >3 min (sin mínimo).\n"
            "  • Min=10 | Max=    → elimina los <10 min (sin máximo).\n"
            "Deja un campo vacío para 'sin límite'."
        )
        ttk.Label(win, text=help_txt, justify="left",
                  foreground="#555", wraplength=380)\
            .grid(row=3, column=0, columnspan=2,
                  padx=5, pady=(0, 10), sticky="w")

        def delete():
            pid = pid_var.get().strip()
            if not pid:
                messagebox.showwarning("Atención",
                                       "Ingresa el ID de la playlist.")
                return
            try:
                min_sec = int(float(min_var.get()) * 60) if min_var.get() else None
            except ValueError:
                messagebox.showerror("Error", "Duración mínima inválida.")
                return
            try:
                max_sec = int(float(max_var.get()) * 60) if max_var.get() else None
            except ValueError:
                messagebox.showerror("Error", "Duración máxima inválida.")
                return

            self.update_status("Eliminando videos por duración...")

            def worker():
                mgr = YouTubeManager(
                    self.token_file.get(),
                    ["https://www.googleapis.com/auth/youtube.force-ssl"],
                    log_queue=self.log_queue
                )
                removed = mgr.remove_videos_by_duration(
                    pid, min_sec, max_sec)
                messagebox.showinfo(
                    "Éxito",
                    f"Eliminados {removed} videos de la playlist."
                )
                self.refresh_playlists()
                win.destroy()

            threading.Thread(target=worker, daemon=True).start()

        ttk.Button(win, text="Eliminar Videos", command=delete)\
            .grid(row=4, column=0, columnspan=2, pady=10)
        win.grid_columnconfigure(0, weight=1)
        win.grid_columnconfigure(1, weight=1)

    # ------------------------------------------------------------------ #
    # 9. TOKEN / CONFIG / AUTO-UPDATE
    # ------------------------------------------------------------------ #
    def update_token_action(self):
        path = filedialog.askopenfilename(
            title="Selecciona client_secrets.json",
            filetypes=[("JSON Files", "*.json")]
        )
        if not path:
            return
        try:
            YouTubeManager.update_token_pickle(
                self.token_file.get(), path,
                ["https://www.googleapis.com/auth/youtube.force-ssl"]
            )
            messagebox.showinfo("Éxito", "Token actualizado correctamente.")
        except Exception as e:
            messagebox.showerror("Error",
                                 f"No se pudo actualizar el token: {e}")

    def open_config_window(self):
        """Ajustes globales — incluye tip de ejemplo de duración."""
        win = tk.Toplevel(self.root)
        win.title("Configuración")

        def add_row(text, var, row):
            ttk.Label(win, text=text)\
                .grid(row=row, column=0, padx=5, pady=5, sticky="w")
            ttk.Entry(win, textvariable=var, width=20)\
                .grid(row=row, column=1, padx=5, pady=5, sticky="ew")

        retry_var = tk.IntVar(value=self.config["retry_delay"])
        batch_var = tk.IntVar(value=self.config["batch_size"])
        excl_var  = tk.StringVar(value=self.config["filter_exclude_keywords"])
        mind_var  = tk.IntVar(value=self.config["filter_min_duration"] // 60)
        maxd_var  = tk.IntVar(value=self.config["filter_max_duration"] // 60)
        au_var    = tk.IntVar(value=self.config["auto_update_interval"])

        add_row("Tiempo de reintento (seg):", retry_var, 0)
        add_row("Videos por lote:",            batch_var, 1)
        add_row("Excluir Palabras (coma):",    excl_var,  2)
        add_row("Duración mínima (min):",      mind_var,  3)
        add_row("Duración máxima (min):",      maxd_var,  4)

        # Tip de ejemplo
        ttk.Label(
            win,
            text="Ejemplo: 1-20 = entre 1 y 20 min (0 = sin límite).",
            foreground="#555"
        ).grid(row=5, column=0, columnspan=2, padx=5, sticky="w")

        add_row("Auto actualización (min):",   au_var,    6)

        def save():
            self.config["retry_delay"]            = retry_var.get()
            self.config["batch_size"]             = batch_var.get()
            self.config["filter_exclude_keywords"]= excl_var.get()
            self.config["filter_min_duration"]    = mind_var.get() * 60
            self.config["filter_max_duration"]    = maxd_var.get() * 60
            self.config["auto_update_interval"]   = au_var.get()
            self.logger.info("Configuración actualizada.")
            win.destroy()
            if self.config["auto_update_interval"] > 0:
                self.start_auto_update()

        ttk.Button(win, text="Guardar", command=save)\
            .grid(row=7, column=0, columnspan=2, pady=10)
        win.grid_columnconfigure(0, weight=1)
        win.grid_columnconfigure(1, weight=1)

    def start_auto_update(self):
        def worker():
            self.logger.info("Actualización automática iniciada.")
            while self.config["auto_update_interval"] > 0:
                time.sleep(self.config["auto_update_interval"] * 60)
                if self.batch_channels and self.playlist_id.get().strip():
                    self.process_batch_action()

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    # 10. RECOMENDACIONES, LOG, AYUDA
    # ------------------------------------------------------------------ #
    def recommendations_action(self):
        def worker():
            mgr = YouTubeManager(
                self.token_file.get(),
                ["https://www.googleapis.com/auth/youtube.force-ssl"],
                log_queue=self.log_queue
            )
            trending = mgr.get_trending_videos(
                regionCode='US', maxResults=10)
            self.root.after(0,
                            lambda: self._show_recommendations(trending))

        threading.Thread(target=worker, daemon=True).start()

    def _show_recommendations(self, items: list[dict]):
        win = tk.Toplevel(self.root)
        win.title("Recomendaciones - Trending Videos")
        win.geometry("500x400")
        frame = ttk.Frame(win, padding=5)
        frame.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical")
        lb = tk.Listbox(frame, yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.config(command=lb.yview)
        sb.pack(side="right", fill="y")
        for it in items:
            lb.insert(tk.END, f"{it['snippet']['title']} (ID: {it['id']})")
        ttk.Button(win, text="Cerrar", command=win.destroy)\
            .pack(pady=5)

    def view_log_history(self):
        try:
            with open("ytube.log", "r", encoding="utf-8",
                      errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error",
                                 f"No se pudo leer el log: {e}")
            return
        win = tk.Toplevel(self.root)
        win.title("Historial de Log")
        win.geometry("600x400")
        txt = scrolledtext.ScrolledText(win, wrap="word")
        txt.insert(tk.END, content)
        txt.configure(state='disabled')
        txt.pack(padx=10, pady=10, fill="both", expand=True)
        ttk.Button(win, text="Cerrar",
                   command=win.destroy).pack(pady=5)

    def export_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log Files", "*.log"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            with open("ytube.log", "r", encoding="utf-8",
                      errors="replace") as src, \
                 open(path, "w", encoding="utf-8",
                      errors="replace") as dst:
                dst.write(src.read())
            messagebox.showinfo("Éxito", f"Log exportado a {path}")
        except Exception as e:
            messagebox.showerror("Error",
                                 f"No se pudo exportar el log: {e}")

    def open_help_window(self):
        help_text = (
            "Instrucciones de uso:\n\n"
            "- Usa la pestaña 'Búsqueda y Canal' para buscar canales y ver detalles.\n"
            "- Agrega canales a 'Batch Processing' y procesa en lote para actualizar una playlist.\n"
            "- En 'Playlists' puedes ver, crear, actualizar, borrar y vaciar tus playlists.\n"
            "- Filtra videos por palabras clave y duración (minutos).\n"
            "- Configura la actualización automática en 'Configuración'.\n"
            "- 'Recomendaciones' muestra videos en tendencia.\n"
            "- Revisa 'Ver Historial' o guarda el log con 'Exportar Log'."
        )
        win = tk.Toplevel(self.root)
        win.title("Ayuda")
        win.geometry("600x400")
        txt = scrolledtext.ScrolledText(win, wrap="word")
        txt.insert(tk.END, help_text)
        txt.configure(state='disabled')
        txt.pack(padx=10, pady=10, fill="both", expand=True)
        ttk.Button(win, text="Cerrar",
                   command=win.destroy).pack(pady=5)

    def share_results(self):
        summary = (f"Estado: {self.status_var.get()}\n"
                   f"Progreso: {self.progress_value.get():.1f}%")
        self.root.clipboard_clear()
        self.root.clipboard_append(summary)
        messagebox.showinfo("Compartir",
                            "Resumen copiado al portapapeles.")


# ---------------------------------------------------------------------- #
# EJECUCIÓN DIRECTA
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
