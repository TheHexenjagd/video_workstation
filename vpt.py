import configparser
import json
import os
import queue
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# -----------------------------
# CONFIGURACION VPT
# -----------------------------
CONFIG_DIR = os.path.join(os.getenv("APPDATA"), "Galleon", "VPT")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "vpt_config.ini")

FFMPEG_DIR = os.path.join(os.getenv("APPDATA"), "Galleon", "bin")
os.makedirs(FFMPEG_DIR, exist_ok=True)

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".ts", ".m4v")
BITMAP_SUB_CODECS = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub", "dvb_teletext"}

PRESETS_NVIDIA = {
    "lossless": {"nombre": "Lossless", "descripcion": "Sin perdida", "velocidad": "⚡☆☆", "calidad": "★★★★★"},
    "hq": {"nombre": "HQ", "descripcion": "Prioriza calidad", "velocidad": "⚡☆☆", "calidad": "★★★★☆"},
    "slow": {"nombre": "Slow (HQ)", "descripcion": "Mejor calidad, menor velocidad", "velocidad": "⚡☆☆", "calidad": "★★★★"},
    "bd": {"nombre": "BD", "descripcion": "Compatibilidad Blu-ray", "velocidad": "⚡☆☆", "calidad": "★★★★"},
    "default": {"nombre": "Default", "descripcion": "Balance entre calidad y velocidad", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "medium": {"nombre": "Medium", "descripcion": "Calidad intermedia", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "llhq": {"nombre": "LLHQ", "descripcion": "Baja latencia + calidad", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "fast": {"nombre": "Fast", "descripcion": "Mas rapido, algo menos eficiente", "velocidad": "⚡⚡⚡", "calidad": "★★☆☆"},
    "ll": {"nombre": "LL", "descripcion": "Baja latencia", "velocidad": "⚡⚡⚡", "calidad": "★★☆☆"},
    "llhp": {"nombre": "LLHP", "descripcion": "Baja latencia + rendimiento", "velocidad": "⚡⚡⚡", "calidad": "★★☆☆"},
    "hp": {"nombre": "HP", "descripcion": "Prioriza velocidad", "velocidad": "⚡⚡⚡⚡", "calidad": "★★☆☆"},
}

PRESETS_QSV = {
    "veryslow": {"nombre": "Very Slow", "descripcion": "Maxima calidad", "velocidad": "⚡☆☆", "calidad": "★★★★★"},
    "slow": {"nombre": "Slow", "descripcion": "Mejor calidad", "velocidad": "⚡☆☆", "calidad": "★★★★"},
    "medium": {"nombre": "Medium", "descripcion": "Calidad mejor, algo mas lento", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "fast": {"nombre": "Fast", "descripcion": "Balance velocidad/calidad", "velocidad": "⚡⚡⚡", "calidad": "★★★☆"},
    "faster": {"nombre": "Faster", "descripcion": "Rapido", "velocidad": "⚡⚡⚡", "calidad": "★★☆☆"},
    "veryfast": {"nombre": "Very Fast", "descripcion": "Maxima velocidad", "velocidad": "⚡⚡⚡⚡", "calidad": "★★☆☆"},
}

DEFAULT_CONFIG = {
    "Paths": {
        "ffmpeg": os.path.join(FFMPEG_DIR, "ffmpeg.exe"),
        "ffprobe": os.path.join(FFMPEG_DIR, "ffprobe.exe"),
        "output_dir": "",
    },
    "Options": {
        "buscar_recursivo": "True",
        "backup_original": "True",
        "crear_subcarpeta": "False",
        "nombre_subcarpeta": "{name}/Peliculas",
        "usar_nvidia": "True",
        "preset": "medium",
    },
}


def obtener_identificador_pista(stream):
    tags = stream.get("tags", {})
    return f"{tags.get('language', 'und')}|{tags.get('title', '')}|{stream.get('codec_name', 'unknown')}"


def encontrar_pista_por_identificador(streams, identificador, codec_type):
    if identificador in (None, "NINGUNO"):
        return None

    parts = identificador.split("|")
    if len(parts) >= 3:
        lang_buscado = parts[0]
        codec_buscado = parts[-1]
        title_buscado = "|".join(parts[1:-1])
    elif len(parts) == 2:
        lang_buscado, codec_buscado = parts
        title_buscado = ""
    else:
        lang_buscado = parts[0] if parts else ""
        title_buscado = ""
        codec_buscado = ""

    for stream in streams:
        if stream.get("codec_type") != codec_type:
            continue
        tags = stream.get("tags", {})
        if (
            tags.get("language", "und") == lang_buscado
            and tags.get("title", "") == title_buscado
            and stream.get("codec_name", "unknown") == codec_buscado
        ):
            return stream["index"]

    for stream in streams:
        if stream.get("codec_type") != codec_type:
            continue
        tags = stream.get("tags", {})
        if tags.get("language", "und") == lang_buscado and tags.get("title", "") == title_buscado:
            return stream["index"]

    for stream in streams:
        if stream.get("codec_type") == codec_type:
            return stream["index"]

    return None


def obtener_preset_valido(preset, usar_nvidia):
    if usar_nvidia:
        if preset in PRESETS_NVIDIA:
            return preset
        mapeo = {
            "veryfast": "hp",
            "faster": "fast",
            "fast": "fast",
            "medium": "medium",
            "slow": "slow",
            "veryslow": "hq",
        }
        return mapeo.get(preset, "default")

    if preset in PRESETS_QSV:
        return preset
    mapeo = {
        "default": "medium",
        "slow": "slow",
        "medium": "medium",
        "fast": "fast",
        "hp": "veryfast",
        "hq": "slow",
        "bd": "slow",
        "ll": "fast",
        "llhq": "medium",
        "llhp": "faster",
        "lossless": "veryslow",
    }
    return mapeo.get(preset, "medium")


class VPTSuite:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VPT Studio - Video Processing Toolkit")
        self.root.geometry("1220x820")
        self.root.minsize(1100, 740)

        self.config_ini = self._cargar_configuracion()
        self.ffmpeg_path = self.config_ini.get("Paths", "ffmpeg", fallback=DEFAULT_CONFIG["Paths"]["ffmpeg"])
        self.ffprobe_path = self.config_ini.get("Paths", "ffprobe", fallback=DEFAULT_CONFIG["Paths"]["ffprobe"])

        self.msg_queue = queue.Queue()
        self.procesando = False
        self.cancelar_procesamiento = False
        self.nvenc_verificado = None

        self.pistas_config = {"audio_tag": None, "subtitle_tag": None, "aplicar_a_todos": False}
        self.combinaciones_a_aplicar = {"combinaciones": [], "aplicar_a_todos": False}

        self._crear_estilos()
        self._crear_menu()
        self._crear_ui()
        self._verificar_ffmpeg_inicio()

        self.root.protocol("WM_DELETE_WINDOW", self.salir_aplicacion)

    # -----------------------------
    # Configuracion
    # -----------------------------
    def _cargar_configuracion(self):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            try:
                config.read(CONFIG_FILE, encoding="utf-8")
            except Exception:
                for section, values in DEFAULT_CONFIG.items():
                    config[section] = values
                self._guardar_configuracion(config)
        else:
            for section, values in DEFAULT_CONFIG.items():
                config[section] = values
            self._guardar_configuracion(config)
        return config

    def _guardar_configuracion(self, config=None):
        cfg = config if config else self.config_ini
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                cfg.write(f)
        except Exception as exc:
            print(f"Error guardando configuracion: {exc}")

    def _actualizar_configuracion(self, *_):
        try:
            self.config_ini["Paths"] = {
                "ffmpeg": self.ffmpeg_path,
                "ffprobe": self.ffprobe_path,
                "output_dir": self.salida_var.get(),
            }
            self.config_ini["Options"] = {
                "buscar_recursivo": str(self.var_recursivo.get()),
                "backup_original": str(self.var_backup.get()),
                "crear_subcarpeta": str(self.var_subcarpeta.get()),
                "nombre_subcarpeta": self.var_nombre_subcarpeta.get(),
                "usar_nvidia": str(self.var_usar_nvidia.get()),
                "preset": self.preset_var.get(),
            }
            self._guardar_configuracion()
        except Exception as exc:
            print(f"Error actualizando configuracion: {exc}")

    # -----------------------------
    # UI moderna
    # -----------------------------
    def _crear_estilos(self):
        self.root.configure(bg="#F3F7FF")
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("VPT.TFrame", background="#F3F7FF")
        style.configure("Card.TFrame", background="#FFFFFF")
        style.configure("Header.TLabel", background="#F3F7FF", foreground="#1F2A44", font=("Segoe UI", 19, "bold"))
        style.configure("SubHeader.TLabel", background="#F3F7FF", foreground="#5C6B8A", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#FFFFFF", foreground="#2B3A57", font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background="#FFFFFF", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(16, 8), background="#DDE8FF", foreground="#2B3A57")
        style.map("TNotebook.Tab", background=[("selected", "#2D9CDB")], foreground=[("selected", "#FFFFFF")])
        style.configure("Modern.Horizontal.TProgressbar", troughcolor="#E5ECF9", background="#2D9CDB", bordercolor="#E5ECF9")

    def _crear_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        archivo = tk.Menu(menubar, tearoff=0)
        archivo.add_command(label="Salir", command=self.salir_aplicacion)
        menubar.add_cascade(label="Archivo", menu=archivo)

        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label="Cambiar ruta de FFmpeg...", command=self.cambiar_ruta_ffmpeg)
        config_menu.add_command(label="Cambiar ruta de FFProbe...", command=self.cambiar_ruta_ffprobe)
        config_menu.add_command(label="Preset de codificacion...", command=self.cambiar_preset)
        config_menu.add_separator()
        config_menu.add_command(label="Info de rutas FFmpeg/FFProbe", command=self.ver_info_ffmpeg)
        menubar.add_cascade(label="Configuracion", menu=config_menu)

        ayuda = tk.Menu(menubar, tearoff=0)
        ayuda.add_command(label="Acerca de...", command=self.mostrar_acerca_de)
        menubar.add_cascade(label="Ayuda", menu=ayuda)

        self.root.bind("<F1>", lambda _: self.mostrar_acerca_de())

    def _crear_ui(self):
        main = ttk.Frame(self.root, style="VPT.TFrame")
        main.pack(fill=tk.BOTH, expand=True)

        hero = ttk.Frame(main, style="VPT.TFrame")
        hero.pack(fill=tk.X, padx=18, pady=(14, 8))
        ttk.Label(hero, text="VPT Studio", style="Header.TLabel").pack(anchor=tk.W)
        ttk.Label(hero, text="Fusion de AudioSubs + HardCode en una interfaz moderna", style="SubHeader.TLabel").pack(anchor=tk.W)

        top = ttk.Frame(main, style="VPT.TFrame")
        top.pack(fill=tk.BOTH, expand=True, padx=18, pady=6)

        left = ttk.Frame(top, style="Card.TFrame")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8), pady=4)

        ttk.Label(left, text="Cola de videos", style="CardTitle.TLabel").pack(anchor=tk.W, padx=12, pady=(10, 6))
        self.lista = tk.Listbox(left, selectmode=tk.EXTENDED, bg="#F9FBFF", fg="#1F2A44", selectbackground="#2D9CDB", selectforeground="#FFFFFF", relief=tk.FLAT, font=("Consolas", 10))
        self.lista.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        acciones = tk.Frame(left, bg="#FFFFFF")
        acciones.pack(fill=tk.X, padx=12, pady=(0, 10))

        self._btn(acciones, "Agregar", self.seleccionar_archivos, "#2F80ED").pack(side=tk.LEFT, padx=3)
        self._btn(acciones, "Cargar carpeta", self.cargar_carpeta, "#2F80ED").pack(side=tk.LEFT, padx=3)
        self._btn(acciones, "Quitar seleccion", self.eliminar_seleccionados, "#F2994A").pack(side=tk.LEFT, padx=3)
        self._btn(acciones, "Limpiar", self.limpiar_lista, "#EB5757").pack(side=tk.LEFT, padx=3)

        right = ttk.Frame(top, style="Card.TFrame")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=4)

        ttk.Label(right, text="Modulos", style="CardTitle.TLabel").pack(anchor=tk.W, padx=12, pady=(10, 6))
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        self.tab_asrt = ttk.Frame(self.tabs, style="Card.TFrame")
        self.tab_hst = ttk.Frame(self.tabs, style="Card.TFrame")
        self.tab_tools = ttk.Frame(self.tabs, style="Card.TFrame")

        self.tabs.add(self.tab_asrt, text="Versiones Audio/Sub")
        self.tabs.add(self.tab_hst, text="Hardcode")
        self.tabs.add(self.tab_tools, text="Mantenimiento")

        self._crear_tab_asrt()
        self._crear_tab_hst()
        self._crear_tab_tools()

        base = ttk.Frame(main, style="Card.TFrame")
        base.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 14))

        opts = tk.Frame(base, bg="#FFFFFF")
        opts.pack(fill=tk.X, padx=12, pady=(12, 8))

        self.var_recursivo = tk.BooleanVar(value=self.config_ini.getboolean("Options", "buscar_recursivo", fallback=True))
        self.var_backup = tk.BooleanVar(value=self.config_ini.getboolean("Options", "backup_original", fallback=True))
        self.var_subcarpeta = tk.BooleanVar(value=self.config_ini.getboolean("Options", "crear_subcarpeta", fallback=False))
        self.var_nombre_subcarpeta = tk.StringVar(value=self.config_ini.get("Options", "nombre_subcarpeta", fallback="{name}/Peliculas"))
        self.var_usar_nvidia = tk.BooleanVar(value=self.config_ini.getboolean("Options", "usar_nvidia", fallback=True))
        self.preset_var = tk.StringVar(value=self.config_ini.get("Options", "preset", fallback="medium"))
        self.salida_var = tk.StringVar(value=self.config_ini.get("Paths", "output_dir", fallback=""))

        for var in [
            self.var_recursivo,
            self.var_backup,
            self.var_subcarpeta,
            self.var_nombre_subcarpeta,
            self.var_usar_nvidia,
            self.preset_var,
            self.salida_var,
        ]:
            var.trace_add("write", self._actualizar_configuracion)

        tk.Checkbutton(opts, text="Buscar recursivo", variable=self.var_recursivo, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=8)
        tk.Checkbutton(opts, text="Backup original", variable=self.var_backup, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=8)
        tk.Checkbutton(opts, text="Crear subcarpeta", variable=self.var_subcarpeta, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=8)
        tk.Entry(opts, textvariable=self.var_nombre_subcarpeta, width=24, bg="#F4F8FF", fg="#1F2A44", relief=tk.FLAT).pack(side=tk.LEFT, padx=6)
        tk.Checkbutton(opts, text="Usar NVIDIA", variable=self.var_usar_nvidia, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF", command=self._on_gpu_change).pack(side=tk.LEFT, padx=8)

        salida = tk.Frame(base, bg="#FFFFFF")
        salida.pack(fill=tk.X, padx=12, pady=6)
        tk.Label(salida, text="Salida:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        tk.Entry(salida, textvariable=self.salida_var, bg="#F4F8FF", fg="#1F2A44", relief=tk.FLAT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self._btn(salida, "Seleccionar", self.seleccionar_directorio, "#4DA8DA").pack(side=tk.LEFT)

        prog = tk.Frame(base, bg="#FFFFFF")
        prog.pack(fill=tk.X, padx=12, pady=(4, 8))
        self.progress_label = tk.Label(prog, text="Listo", bg="#FFFFFF", fg="#5C6B8A", font=("Segoe UI", 9))
        self.progress_label.pack(anchor=tk.W)
        self.progress = ttk.Progressbar(prog, style="Modern.Horizontal.TProgressbar", mode="determinate")
        self.progress.pack(fill=tk.X, pady=(4, 0))

        tk.Label(base, text="Actividad", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=12)
        log_frame = tk.Frame(base, bg="#FFFFFF")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 10))
        self.log = tk.Text(log_frame, bg="#F9FBFF", fg="#24324A", font=("Consolas", 9), relief=tk.FLAT, state=tk.DISABLED)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scr = tk.Scrollbar(log_frame, command=self.log.yview)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.config(yscrollcommand=scr.set)

    def _btn(self, parent, text, cmd, bg):
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg="white",
            activebackground=bg,
            activeforeground="white",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

    def _crear_tab_asrt(self):
        frm = tk.Frame(self.tab_asrt, bg="#FFFFFF")
        frm.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        tk.Label(frm, text="Genera multiples versiones por combinaciones de audio/subtitulos", bg="#FFFFFF", fg="#5C6B8A", font=("Segoe UI", 10)).pack(anchor=tk.W)
        btns = tk.Frame(frm, bg="#FFFFFF")
        btns.pack(anchor=tk.W, pady=12)
        self.btn_versiones = self._btn(btns, "Generar versiones", self.procesar_versiones, "#2D9CDB")
        self.btn_versiones.pack(side=tk.LEFT, padx=(0, 8))
        self._btn(btns, "Verificar condiciones", self.verificar_condiciones_carpeta, "#27AE60").pack(side=tk.LEFT, padx=(0, 8))
        self.btn_cancelar_asrt = self._btn(btns, "Cancelar", self.cancelar, "#EB5757")
        self.btn_cancelar_asrt.config(state=tk.DISABLED)
        self.btn_cancelar_asrt.pack(side=tk.LEFT, padx=(0, 8))

    def _crear_tab_hst(self):
        frm = tk.Frame(self.tab_hst, bg="#FFFFFF")
        frm.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        tk.Label(frm, text="Hardcode de subtitulos con NVIDIA NVENC o Intel QSV", bg="#FFFFFF", fg="#5C6B8A", font=("Segoe UI", 10)).pack(anchor=tk.W)
        btns = tk.Frame(frm, bg="#FFFFFF")
        btns.pack(anchor=tk.W, pady=12)
        self.btn_hardcode = self._btn(btns, "Procesar hardcode", self.procesar_hardcode, "#56CCF2")
        self.btn_hardcode.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_cancelar_hst = self._btn(btns, "Cancelar", self.cancelar, "#EB5757")
        self.btn_cancelar_hst.config(state=tk.DISABLED)
        self.btn_cancelar_hst.pack(side=tk.LEFT, padx=(0, 8))

    def _crear_tab_tools(self):
        frm = tk.Frame(self.tab_tools, bg="#FFFFFF")
        frm.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        tk.Label(frm, text="Herramientas de mantenimiento", bg="#FFFFFF", fg="#5C6B8A", font=("Segoe UI", 10)).pack(anchor=tk.W)
        btns = tk.Frame(frm, bg="#FFFFFF")
        btns.pack(anchor=tk.W, pady=12)
        self.btn_limpiar_meta = self._btn(btns, "Limpiar metadatos", self.limpiar_metadatos, "#F2C94C")
        self.btn_limpiar_meta.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_cancelar = self._btn(btns, "Cancelar", self.cancelar, "#EB5757")
        self.btn_cancelar.config(state=tk.DISABLED)
        self.btn_cancelar.pack(side=tk.LEFT, padx=(0, 8))

    # -----------------------------
    # Utilidades comunes
    # -----------------------------
    def _enviar_mensaje(self, msg):
        self.msg_queue.put(msg)

    def _append_log(self, msg):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def _actualizar_ui(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if isinstance(msg, tuple):
                    if msg[0] == "PROGRESO":
                        _, actual, total = msg
                        pct = (actual / total) * 100 if total else 0
                        self.progress["value"] = pct
                        self.progress_label.config(text=f"Procesando {actual}/{total} ({pct:.1f}%)")
                    elif msg[0] == "FINALIZADO":
                        _, ok, fail = msg
                        self.progress["value"] = 100
                        self.progress_label.config(text=f"Completado | Exitos: {ok} | Fallos: {fail}")
                        self._set_running_state(False)
                        messagebox.showinfo("Completado", f"Proceso terminado.\n\nExitos: {ok}\nFallos: {fail}")
                    elif msg[0] == "SELECTOR_PISTAS":
                        _, info, filename, q = msg
                        q.put(self._mostrar_selector_pistas(info, filename))
                    elif msg[0] == "SELECTOR_COMBINACIONES":
                        _, info, filename, q = msg
                        q.put(self._mostrar_selector_combinaciones(info, filename))
                else:
                    self._append_log(msg)
        except queue.Empty:
            pass

        if self.procesando or not self.msg_queue.empty():
            self.root.after(100, self._actualizar_ui)

    def _set_running_state(self, running):
        self.btn_versiones.config(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_hardcode.config(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_limpiar_meta.config(state=tk.DISABLED if running else tk.NORMAL)
        cancel_state = tk.NORMAL if running else tk.DISABLED
        self.btn_cancelar.config(state=cancel_state)
        self.btn_cancelar_asrt.config(state=cancel_state)
        self.btn_cancelar_hst.config(state=cancel_state)

    def _ffprobe_info(self, filepath):
        filepath = os.path.abspath(os.path.normpath(filepath))
        if len(filepath) > 260 and not filepath.startswith("\\\\?\\"):
            filepath = "\\\\?\\" + filepath

        cmd = [self.ffprobe_path, "-v", "error", "-print_format", "json", "-show_streams", filepath]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            self._enviar_mensaje(f"❌ Error ffprobe: {result.stderr[:220]}")
            return None

        try:
            data = json.loads(result.stdout)
            if "streams" not in data:
                return None
            return data
        except json.JSONDecodeError:
            return None

    def _verificar_ffmpeg_inicio(self):
        if os.path.exists(self.ffmpeg_path) and os.path.exists(self.ffprobe_path):
            return
        messagebox.showwarning(
            "FFmpeg/FFprobe no encontrados",
            "No se detectaron las rutas configuradas. Selecciona ffmpeg.exe y ffprobe.exe para continuar.",
        )
        self.cambiar_ruta_ffmpeg()
        if not os.path.exists(self.ffprobe_path):
            self.cambiar_ruta_ffprobe()

    def _on_gpu_change(self):
        preset_actual = self.preset_var.get()
        nuevo = obtener_preset_valido(preset_actual, self.var_usar_nvidia.get())
        if nuevo != preset_actual:
            self.preset_var.set(nuevo)

    def _nvidia_disponible(self):
        if self.nvenc_verificado is not None:
            return self.nvenc_verificado

        if not os.path.exists(self.ffmpeg_path):
            self.nvenc_verificado = (False, "FFmpeg no encontrado")
            return self.nvenc_verificado

        encoders = subprocess.run([self.ffmpeg_path, "-hide_banner", "-encoders"], capture_output=True, text=True)
        if encoders.returncode != 0 or "h264_nvenc" not in encoders.stdout:
            self.nvenc_verificado = (False, "h264_nvenc no disponible")
            return self.nvenc_verificado

        test = subprocess.run(
            [
                self.ffmpeg_path,
                "-hide_banner",
                "-f",
                "lavfi",
                "-i",
                "nullsrc=s=256x256:d=1",
                "-c:v",
                "h264_nvenc",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
        )
        if test.returncode != 0:
            self.nvenc_verificado = (False, "NVENC no se pudo inicializar")
            return self.nvenc_verificado

        self.nvenc_verificado = (True, "NVENC OK")
        return self.nvenc_verificado

    # -----------------------------
    # Selectores
    # -----------------------------
    def _mostrar_selector_pistas(self, info, filename):
        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]

        if len(audio_streams) <= 1 and len(subtitle_streams) == 0:
            return {
                "ok": True,
                "audio": obtener_identificador_pista(audio_streams[0]) if audio_streams else None,
                "subtitle": "NINGUNO",
                "aplicar_todos": False,
            }

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Seleccion de pistas - {os.path.basename(filename)}")
        dialog.geometry("740x620")
        dialog.transient(self.root)
        dialog.grab_set()

        resultado = {"ok": False, "audio": None, "subtitle": "NINGUNO", "aplicar_todos": False}

        tk.Label(dialog, text=f"Archivo: {os.path.basename(filename)}", font=("Segoe UI", 10, "bold")).pack(pady=(10, 6))

        body = tk.Frame(dialog)
        body.pack(fill=tk.BOTH, expand=True, padx=10)

        audio_var = tk.StringVar(value=obtener_identificador_pista(audio_streams[0]) if audio_streams else "")
        sub_var = tk.StringVar(value="NINGUNO")

        lf_audio = tk.LabelFrame(body, text="Audio", font=("Segoe UI", 9, "bold"))
        lf_audio.pack(fill=tk.BOTH, expand=True, pady=6)
        for i, s in enumerate(audio_streams):
            tags = s.get("tags", {})
            title = tags.get("title") or f"Audio {i + 1}"
            lang = tags.get("language", "und")
            codec = s.get("codec_name", "unknown")
            tk.Radiobutton(lf_audio, text=f"{title} ({lang}) - {codec}", variable=audio_var, value=obtener_identificador_pista(s), anchor=tk.W).pack(fill=tk.X, padx=6, pady=2)

        lf_sub = tk.LabelFrame(body, text="Subtitulos", font=("Segoe UI", 9, "bold"))
        lf_sub.pack(fill=tk.BOTH, expand=True, pady=6)
        tk.Radiobutton(lf_sub, text="Sin subtitulos", variable=sub_var, value="NINGUNO", anchor=tk.W).pack(fill=tk.X, padx=6, pady=2)
        for i, s in enumerate(subtitle_streams):
            tags = s.get("tags", {})
            title = tags.get("title") or f"Subtitulo {i + 1}"
            lang = tags.get("language", "und")
            codec = s.get("codec_name", "unknown")
            tk.Radiobutton(lf_sub, text=f"{title} ({lang}) - {codec}", variable=sub_var, value=obtener_identificador_pista(s), anchor=tk.W).pack(fill=tk.X, padx=6, pady=2)

        apply_all = tk.BooleanVar(value=False)
        tk.Checkbutton(dialog, text="Aplicar seleccion a todos los archivos", variable=apply_all).pack(pady=6)

        btns = tk.Frame(dialog)
        btns.pack(pady=10)

        def aceptar():
            resultado["ok"] = True
            resultado["audio"] = audio_var.get()
            resultado["subtitle"] = sub_var.get()
            resultado["aplicar_todos"] = apply_all.get()
            dialog.destroy()

        tk.Button(btns, text="Aceptar", command=aceptar, bg="#2D9CDB", fg="white", width=14).pack(side=tk.LEFT, padx=6)
        tk.Button(btns, text="Cancelar", command=dialog.destroy, bg="#EB5757", fg="white", width=14).pack(side=tk.LEFT, padx=6)

        dialog.wait_window()
        return resultado

    def _mostrar_selector_combinaciones(self, info, filename):
        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]

        if not audio_streams and not subtitle_streams:
            return {"ok": True, "combinaciones": [], "aplicar_todos": False}

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Versiones a generar - {os.path.basename(filename)}")
        dialog.geometry("900x620")
        dialog.transient(self.root)
        dialog.grab_set()

        resultado = {"ok": False, "combinaciones": [], "aplicar_todos": False}
        combinaciones = []

        tk.Label(dialog, text="Marca pistas para cada version y agrega", font=("Segoe UI", 10, "bold")).pack(pady=8)

        body = tk.Frame(dialog)
        body.pack(fill=tk.BOTH, expand=True, padx=10)

        left = tk.LabelFrame(body, text="Pistas disponibles")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        audio_vars = []
        tk.Label(left, text="Audio", fg="#1E8449", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=6, pady=(6, 2))
        for i, s in enumerate(audio_streams):
            tags = s.get("tags", {})
            title = tags.get("title") or f"Audio {i + 1}"
            lang = tags.get("language", "und")
            var = tk.BooleanVar(value=False)
            audio_vars.append((var, s))
            tk.Checkbutton(left, text=f"{title} ({lang})", variable=var, anchor=tk.W).pack(fill=tk.X, padx=8, pady=2)

        tk.Label(left, text="Subtitulos", fg="#2980B9", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=6, pady=(8, 2))
        sub_vars = []
        for i, s in enumerate(subtitle_streams):
            tags = s.get("tags", {})
            title = tags.get("title") or f"Sub {i + 1}"
            lang = tags.get("language", "und")
            var = tk.BooleanVar(value=False)
            sub_vars.append((var, s))
            tk.Checkbutton(left, text=f"{title} ({lang})", variable=var, anchor=tk.W).pack(fill=tk.X, padx=8, pady=2)

        right = tk.LabelFrame(body, text="Versiones")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        lst = tk.Listbox(right, font=("Consolas", 9))
        lst.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        def refresh():
            lst.delete(0, tk.END)
            for i, combo in enumerate(combinaciones):
                lst.insert(tk.END, f"{i + 1}. {combo['label']}")

        def agregar():
            aud_sel = [s for var, s in audio_vars if var.get()]
            sub_sel = [s for var, s in sub_vars if var.get()]
            if not aud_sel and not sub_sel:
                messagebox.showwarning("Sin seleccion", "Selecciona al menos una pista", parent=dialog)
                return

            audio_indices = [s["index"] for s in aud_sel]
            sub_indices = [s["index"] for s in sub_sel]
            audio_ids = [obtener_identificador_pista(s) for s in aud_sel]
            sub_ids = [obtener_identificador_pista(s) for s in sub_sel]

            audio_langs = [s.get("tags", {}).get("language", "und").upper() for s in aud_sel]
            sub_langs = [s.get("tags", {}).get("language", "und").upper() for s in sub_sel]

            parts = ["_".join(audio_langs)] if audio_langs else []
            if sub_langs:
                parts.append("sub" + "_".join(sub_langs))
            label = "_".join(parts) if parts else "VERSION"

            combinaciones.append(
                {
                    "audio_indices": audio_indices,
                    "sub_indices": sub_indices,
                    "audio_identifiers": audio_ids,
                    "sub_identifiers": sub_ids,
                    "label": label,
                }
            )
            refresh()
            for var, _ in audio_vars:
                var.set(False)
            for var, _ in sub_vars:
                var.set(False)

        def quitar():
            sel = lst.curselection()
            if sel:
                del combinaciones[sel[0]]
                refresh()

        bt = tk.Frame(right)
        bt.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(bt, text="Agregar version", command=agregar, bg="#27AE60", fg="white").pack(side=tk.LEFT, padx=4)
        tk.Button(bt, text="Quitar", command=quitar, bg="#EB5757", fg="white").pack(side=tk.LEFT, padx=4)

        apply_all = tk.BooleanVar(value=False)
        tk.Checkbutton(dialog, text="Aplicar esta configuracion a todos los archivos", variable=apply_all).pack(pady=4)

        bottom = tk.Frame(dialog)
        bottom.pack(pady=10)

        def aceptar():
            if not combinaciones:
                messagebox.showwarning("Sin versiones", "Agrega al menos una version", parent=dialog)
                return
            resultado["ok"] = True
            resultado["combinaciones"] = list(combinaciones)
            resultado["aplicar_todos"] = apply_all.get()
            dialog.destroy()

        tk.Button(bottom, text="Aceptar", command=aceptar, bg="#2D9CDB", fg="white", width=14).pack(side=tk.LEFT, padx=6)
        tk.Button(bottom, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=14).pack(side=tk.LEFT, padx=6)

        dialog.wait_window()
        return resultado

    # -----------------------------
    # Procesamiento ASRT
    # -----------------------------
    def _obtener_combinaciones_a_generar(self, info, filename):
        if self.combinaciones_a_aplicar["aplicar_a_todos"]:
            combos = []
            for c in self.combinaciones_a_aplicar["combinaciones"]:
                audio_indices = [
                    encontrar_pista_por_identificador(info["streams"], ident, "audio")
                    for ident in c.get("audio_identifiers", [])
                ]
                audio_indices = [x for x in audio_indices if x is not None]

                sub_indices = [
                    encontrar_pista_por_identificador(info["streams"], ident, "subtitle")
                    for ident in c.get("sub_identifiers", [])
                ]
                sub_indices = [x for x in sub_indices if x is not None]

                if audio_indices or sub_indices:
                    combos.append(
                        {
                            "audio_indices": audio_indices,
                            "sub_indices": sub_indices,
                            "audio_identifiers": c.get("audio_identifiers", []),
                            "sub_identifiers": c.get("sub_identifiers", []),
                            "label": c["label"],
                        }
                    )
            return combos

        q = queue.Queue()
        self.msg_queue.put(("SELECTOR_COMBINACIONES", info, filename, q))
        try:
            r = q.get(timeout=300)
        except queue.Empty:
            return None

        if not r.get("ok"):
            return None

        if r.get("aplicar_todos"):
            self.combinaciones_a_aplicar = {
                "aplicar_a_todos": True,
                "combinaciones": [
                    {
                        "audio_identifiers": c.get("audio_identifiers", []),
                        "sub_identifiers": c.get("sub_identifiers", []),
                        "label": c["label"],
                    }
                    for c in r["combinaciones"]
                ],
            }

        return r["combinaciones"]

    def _generar_combinaciones(self, input_file, output_dir, info, combinaciones):
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
        video_stem = Path(input_file).stem

        ok = 0
        fail = 0

        for i, combo in enumerate(combinaciones, 1):
            audio_indices = combo.get("audio_indices", [])
            sub_indices = combo.get("sub_indices", [])
            label = combo.get("label", "VERSION")

            sub_incluir = []
            excluidos = 0
            for idx in sub_indices:
                s = next((st for st in subtitle_streams if st["index"] == idx), None)
                if s and s.get("codec_name", "").lower() in BITMAP_SUB_CODECS:
                    excluidos += 1
                else:
                    sub_incluir.append(idx)

            if excluidos:
                self._enviar_mensaje(f"⚠️ {excluidos} subtitulos bitmap excluidos")

            out_dir = Path(output_dir)
            if self.var_subcarpeta.get():
                patron = (self.var_nombre_subcarpeta.get().strip() or "{name}/Peliculas").replace("{name}", f"{video_stem}_{label}")
                out_dir = out_dir / Path(patron)

            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"{video_stem}_{label}.mp4"

            cmd = [self.ffmpeg_path, "-i", input_file]
            for s in info["streams"]:
                if s.get("codec_type") not in ("audio", "subtitle"):
                    cmd.extend(["-map", f"0:{s['index']}"])
            for idx in audio_indices:
                cmd.extend(["-map", f"0:{idx}"])
            for idx in sub_incluir:
                cmd.extend(["-map", f"0:{idx}"])

            cmd.extend(["-c:v", "copy", "-c:a", "copy"])
            if sub_incluir:
                cmd.extend(["-c:s", "mov_text"])
            cmd.extend(["-movflags", "+faststart", "-y", str(output_path)])

            self._enviar_mensaje(f"🎞 [{i}/{len(combinaciones)}] {output_path.name}")
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode == 0:
                ok += 1
            else:
                fail += 1
                self._enviar_mensaje("❌ Error al generar version")

        return ok, fail

    def _eliminar_pistas_versiones(self, archivo, output_dir):
        info = self._ffprobe_info(archivo)
        if info is None:
            self._enviar_mensaje("❌ No se pudo leer streams")
            return False

        v = sum(1 for s in info["streams"] if s.get("codec_type") == "video")
        if v < 1:
            return False

        combinaciones = self._obtener_combinaciones_a_generar(info, archivo)
        if combinaciones is None:
            return False

        return self._generar_combinaciones(archivo, output_dir, info, combinaciones)

    def _thread_versiones(self, archivos, output_dir):
        self.procesando = True
        self.cancelar_procesamiento = False
        self.combinaciones_a_aplicar = {"combinaciones": [], "aplicar_a_todos": False}

        ok = 0
        fail = 0
        total = len(archivos)
        self._enviar_mensaje("===== INICIO VERSIONES =====")

        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._enviar_mensaje("⚠️ Cancelado por usuario")
                break
            self.msg_queue.put(("PROGRESO", i, total))
            self._enviar_mensaje(f"Archivo {i}/{total}: {os.path.basename(archivo)}")
            result = self._eliminar_pistas_versiones(archivo, output_dir)
            if isinstance(result, tuple):
                o, f = result
                ok += o
                fail += f
            elif result:
                ok += 1
            else:
                fail += 1

        self._enviar_mensaje("===== FIN VERSIONES =====")
        self.msg_queue.put(("FINALIZADO", ok, fail))
        self.procesando = False
        self.cancelar_procesamiento = False

    def procesar_versiones(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return
        output = self.salida_var.get().strip()
        if not output:
            messagebox.showerror("Error", "Selecciona un directorio de salida")
            return
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        self._clear_log_and_progress("Preparando versiones...")
        self._set_running_state(True)
        threading.Thread(target=self._thread_versiones, args=(archivos, output), daemon=True).start()
        self._actualizar_ui()

    # -----------------------------
    # Verificacion de condiciones
    # -----------------------------
    def verificar_condiciones_carpeta(self):
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showwarning("Sin archivos", "No hay archivos cargados")
            return

        resultados = {"conformes": [], "no_conformes": [], "errores": [], "patron_comun": None}
        estadisticas = {}
        info_archivos = {}

        progreso = tk.Toplevel(self.root)
        progreso.title("Analizando")
        progreso.geometry("500x140")
        progreso.transient(self.root)
        progreso.grab_set()

        lbl = tk.Label(progreso, text="Analizando archivos...", font=("Segoe UI", 10, "bold"))
        lbl.pack(pady=(18, 8))
        status = tk.Label(progreso, text="Preparando...", font=("Segoe UI", 9))
        status.pack()
        pbar = ttk.Progressbar(progreso, mode="determinate", maximum=len(archivos), length=420)
        pbar.pack(pady=10)

        def worker():
            for i, archivo in enumerate(archivos, 1):
                status.config(text=f"{i}/{len(archivos)} - {os.path.basename(archivo)}")
                pbar["value"] = i
                progreso.update_idletasks()

                info = self._ffprobe_info(archivo)
                if info is None:
                    resultados["errores"].append({"archivo": archivo, "razon": "No se pudo obtener informacion"})
                    continue

                aud = [s for s in info["streams"] if s.get("codec_type") == "audio"]
                sub = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
                patron = (len(aud), len(sub))
                estadisticas.setdefault(patron, []).append(archivo)
                info_archivos[archivo] = {"audio": aud, "sub": sub, "patron": patron}

            if estadisticas:
                patron_comun = max(estadisticas, key=lambda k: len(estadisticas[k]))
                resultados["patron_comun"] = patron_comun

                for archivo, inf in info_archivos.items():
                    if inf["patron"] == patron_comun:
                        resultados["conformes"].append({"archivo": archivo, "patron": inf["patron"]})
                    else:
                        resultados["no_conformes"].append(
                            {
                                "archivo": archivo,
                                "patron": inf["patron"],
                                "razon": f"Patron {inf['patron'][0]}a/{inf['patron'][1]}s, esperado {patron_comun[0]}a/{patron_comun[1]}s",
                            }
                        )

            progreso.destroy()
            self._mostrar_resultados_verificacion(resultados)

        threading.Thread(target=worker, daemon=True).start()

    def _mostrar_resultados_verificacion(self, resultados):
        win = tk.Toplevel(self.root)
        win.title("Resultados de verificacion")
        win.geometry("980x700")

        header = tk.Frame(win, bg="#1C2541")
        header.pack(fill=tk.X)
        tk.Label(header, text="Analisis estadistico de streams", bg="#1C2541", fg="white", font=("Segoe UI", 14, "bold")).pack(pady=10)

        if resultados.get("patron_comun"):
            p = resultados["patron_comun"]
            tk.Label(header, text=f"Patron comun: {p[0]} audio(s), {p[1]} subtitulo(s)", bg="#1C2541", fg="#4DA8DA", font=("Segoe UI", 10, "bold")).pack(pady=(0, 8))

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        t1 = tk.Frame(nb)
        t2 = tk.Frame(nb)
        t3 = tk.Frame(nb)
        nb.add(t1, text=f"Conformes ({len(resultados['conformes'])})")
        nb.add(t2, text=f"No conformes ({len(resultados['no_conformes'])})")
        nb.add(t3, text=f"Errores ({len(resultados['errores'])})")

        tx1 = tk.Text(t1, font=("Consolas", 9))
        tx1.pack(fill=tk.BOTH, expand=True)
        for i in resultados["conformes"]:
            tx1.insert(tk.END, f"✅ {i['archivo']}\n")
        tx1.config(state=tk.DISABLED)

        tx2 = tk.Text(t2, font=("Consolas", 9), fg="red")
        tx2.pack(fill=tk.BOTH, expand=True)
        for i in resultados["no_conformes"]:
            tx2.insert(tk.END, f"❌ {i['archivo']}\n   {i['razon']}\n\n")
        tx2.config(state=tk.DISABLED)

        tx3 = tk.Text(t3, font=("Consolas", 9), fg="#B9770E")
        tx3.pack(fill=tk.BOTH, expand=True)
        for i in resultados["errores"]:
            tx3.insert(tk.END, f"⚠️ {i['archivo']}\n   {i['razon']}\n\n")
        tx3.config(state=tk.DISABLED)

    # -----------------------------
    # Procesamiento Hardcode
    # -----------------------------
    def _obtener_pistas_hardcode(self, info, filename):
        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]

        if self.pistas_config["aplicar_a_todos"]:
            a_idx = encontrar_pista_por_identificador(info["streams"], self.pistas_config["audio_tag"], "audio")
            s_idx = encontrar_pista_por_identificador(info["streams"], self.pistas_config["subtitle_tag"], "subtitle")
            if a_idx is not None:
                return a_idx, s_idx

        if len(audio_streams) == 1 and len(subtitle_streams) == 1:
            return audio_streams[0]["index"], subtitle_streams[0]["index"]

        q = queue.Queue()
        self.msg_queue.put(("SELECTOR_PISTAS", info, filename, q))

        try:
            r = q.get(timeout=300)
        except queue.Empty:
            return None, None

        if not r.get("ok"):
            return None, None

        if r.get("aplicar_todos"):
            self.pistas_config["audio_tag"] = r["audio"]
            self.pistas_config["subtitle_tag"] = r["subtitle"]
            self.pistas_config["aplicar_a_todos"] = True

        a_idx = encontrar_pista_por_identificador(info["streams"], r["audio"], "audio")
        s_idx = encontrar_pista_por_identificador(info["streams"], r["subtitle"], "subtitle")
        return a_idx, s_idx

    def _hardcode_subtitulo(self, input_file, output_dir):
        info = self._ffprobe_info(input_file)
        if info is None:
            return False

        v = sum(1 for s in info["streams"] if s.get("codec_type") == "video")
        a = sum(1 for s in info["streams"] if s.get("codec_type") == "audio")
        if v < 1 or a < 1:
            return False

        audio_idx, sub_idx = self._obtener_pistas_hardcode(info, input_file)
        if audio_idx is None:
            return False

        audio_codec = None
        for s in info["streams"]:
            if s.get("codec_type") == "audio" and s.get("index") == audio_idx:
                audio_codec = s.get("codec_name")
                break

        audio_settings = ["-c:a", "aac", "-b:a", "320k"] if audio_codec == "flac" else ["-c:a", "copy"]

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        sufijo = "_hardcoded" if sub_idx is not None else "_nosub"
        out_file = out_dir / f"{Path(input_file).stem}{sufijo}.mp4"

        temp_subtitle_path = None

        try:
            if sub_idx is not None:
                tf = tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False, encoding="utf-8")
                temp_subtitle_path = tf.name
                tf.close()

                extract = [self.ffmpeg_path, "-i", input_file, "-map", f"0:{sub_idx}", "-y", temp_subtitle_path]
                res = subprocess.run(extract, capture_output=True, text=True)
                if res.returncode != 0:
                    return False

                esc = temp_subtitle_path.replace("\\", "/").replace(":", "\\:")
                video_filter = f"ass='{esc}',format=yuv420p"
            else:
                video_filter = "format=yuv420p"

            preset = obtener_preset_valido(self.preset_var.get(), self.var_usar_nvidia.get())

            if self.var_usar_nvidia.get():
                cmd = [
                    self.ffmpeg_path,
                    "-i",
                    input_file,
                    "-map",
                    "0:v:0",
                    "-map",
                    f"0:{audio_idx}",
                    "-vf",
                    video_filter,
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    preset,
                    "-profile:v",
                    "high",
                    "-rc",
                    "vbr_hq",
                    "-cq",
                    "23",
                    "-b:v",
                    "5M",
                    "-maxrate",
                    "8M",
                    "-bufsize",
                    "10M",
                    *audio_settings,
                    "-movflags",
                    "+faststart",
                    "-y",
                    str(out_file),
                ]
            else:
                cmd = [
                    self.ffmpeg_path,
                    "-i",
                    input_file,
                    "-map",
                    "0:v:0",
                    "-map",
                    f"0:{audio_idx}",
                    "-vf",
                    video_filter,
                    "-c:v",
                    "h264_qsv",
                    "-preset",
                    preset,
                    "-global_quality",
                    "23",
                    "-b:v",
                    "5M",
                    "-maxrate",
                    "8M",
                    "-bufsize",
                    "10M",
                    *audio_settings,
                    "-movflags",
                    "+faststart",
                    "-y",
                    str(out_file),
                ]

            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode == 0

        finally:
            if temp_subtitle_path and os.path.exists(temp_subtitle_path):
                try:
                    os.unlink(temp_subtitle_path)
                except Exception:
                    pass

    def _thread_hardcode(self, archivos, output_dir):
        self.procesando = True
        self.cancelar_procesamiento = False
        self.nvenc_verificado = None
        self.pistas_config = {"audio_tag": None, "subtitle_tag": None, "aplicar_a_todos": False}

        ok = 0
        fail = 0
        total = len(archivos)

        if self.var_usar_nvidia.get():
            disp, msg = self._nvidia_disponible()
            self._enviar_mensaje(msg)
            if not disp:
                self.msg_queue.put(("FINALIZADO", 0, total))
                self.procesando = False
                return

        self._enviar_mensaje("===== INICIO HARDCODE =====")
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._enviar_mensaje("⚠️ Cancelado por usuario")
                break
            self.msg_queue.put(("PROGRESO", i, total))
            self._enviar_mensaje(f"Archivo {i}/{total}: {os.path.basename(archivo)}")
            if self._hardcode_subtitulo(archivo, output_dir):
                ok += 1
            else:
                fail += 1

        self._enviar_mensaje("===== FIN HARDCODE =====")
        self.msg_queue.put(("FINALIZADO", ok, fail))
        self.procesando = False
        self.cancelar_procesamiento = False

    def procesar_hardcode(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return

        output = self.salida_var.get().strip()
        if not output:
            messagebox.showerror("Error", "Selecciona un directorio de salida")
            return

        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        self._clear_log_and_progress("Preparando hardcode...")
        self._set_running_state(True)
        threading.Thread(target=self._thread_hardcode, args=(archivos, output), daemon=True).start()
        self._actualizar_ui()

    # -----------------------------
    # Mantenimiento
    # -----------------------------
    def _limpiar_metadatos_archivo(self, video_file):
        video_file = Path(video_file)
        temp_output = video_file.parent / f"temp_{video_file.name}"
        cmd = [
            self.ffmpeg_path,
            "-i",
            str(video_file),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-map",
            "0:s?",
            "-c",
            "copy",
            "-map_metadata",
            "-1",
            "-write_id3v1",
            "0",
            "-write_id3v2",
            "0",
            "-id3v2_version",
            "0",
            "-y",
            str(temp_output),
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=3600)
            if res.returncode != 0:
                return False
            if temp_output.exists():
                video_file.unlink()
                ext = video_file.suffix
                if ext != ext.lower():
                    temp_output.rename(video_file.with_suffix(ext.lower()))
                else:
                    temp_output.rename(video_file)
                return True
            return False
        except Exception:
            return False
        finally:
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except Exception:
                    pass

    def _thread_limpiar_metadatos(self, archivos):
        self.procesando = True
        self.cancelar_procesamiento = False

        ok = 0
        fail = 0
        total = len(archivos)
        self._enviar_mensaje("===== INICIO LIMPIEZA METADATOS =====")

        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._enviar_mensaje("⚠️ Cancelado por usuario")
                break
            self.msg_queue.put(("PROGRESO", i, total))
            self._enviar_mensaje(f"Limpiando {i}/{total}: {os.path.basename(archivo)}")
            if self._limpiar_metadatos_archivo(archivo):
                ok += 1
            else:
                fail += 1

        self._enviar_mensaje("===== FIN LIMPIEZA METADATOS =====")
        self.msg_queue.put(("FINALIZADO", ok, fail))
        self.procesando = False
        self.cancelar_procesamiento = False

    def limpiar_metadatos(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        confirm = messagebox.askyesno(
            "Confirmar",
            f"Se limpiaran metadatos en {len(archivos)} archivo(s).\nEsta accion modifica originales.",
            icon="warning",
        )
        if not confirm:
            return

        self._clear_log_and_progress("Preparando limpieza de metadatos...")
        self._set_running_state(True)
        threading.Thread(target=self._thread_limpiar_metadatos, args=(archivos,), daemon=True).start()
        self._actualizar_ui()

    # -----------------------------
    # Acciones UI
    # -----------------------------
    def _clear_log_and_progress(self, status):
        self.log.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self.progress_label.config(text=status)

    def seleccionar_archivos(self):
        files = filedialog.askopenfilenames(title="Seleccionar videos", filetypes=[("Videos", "*.mp4 *.mkv *.mov *.avi *.flv *.webm *.ts *.m4v")])
        for f in files:
            self.lista.insert(tk.END, os.path.normpath(f))

    def cargar_carpeta(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta")
        if not carpeta:
            return

        encontrados = []
        if self.var_recursivo.get():
            for root, _, files in os.walk(carpeta):
                for name in files:
                    if name.lower().endswith(VIDEO_EXTENSIONS):
                        encontrados.append(os.path.join(root, name))
        else:
            for name in os.listdir(carpeta):
                p = os.path.join(carpeta, name)
                if os.path.isfile(p) and name.lower().endswith(VIDEO_EXTENSIONS):
                    encontrados.append(p)

        for f in encontrados:
            self.lista.insert(tk.END, os.path.normpath(f))

        messagebox.showinfo("Carga finalizada", f"Se agregaron {len(encontrados)} archivo(s)")

    def eliminar_seleccionados(self):
        sel = self.lista.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona elementos")
            return
        for i in reversed(sel):
            self.lista.delete(i)

    def limpiar_lista(self):
        if self.lista.size() == 0:
            return
        if messagebox.askyesno("Confirmar", "Deseas limpiar toda la lista?"):
            self.lista.delete(0, tk.END)

    def seleccionar_directorio(self):
        carpeta = filedialog.askdirectory(title="Seleccionar salida")
        if carpeta:
            self.salida_var.set(carpeta)

    def cancelar(self):
        if not self.procesando:
            messagebox.showinfo("Sin proceso", "No hay procesamiento activo")
            return
        if messagebox.askyesno("Cancelar", "Deseas cancelar el procesamiento actual?"):
            self.cancelar_procesamiento = True
            self.btn_cancelar.config(state=tk.DISABLED)
            self.btn_cancelar_asrt.config(state=tk.DISABLED)
            self.btn_cancelar_hst.config(state=tk.DISABLED)
            self._enviar_mensaje("⚠️ Solicitud de cancelacion enviada...")

    def cambiar_ruta_ffmpeg(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar ffmpeg.exe",
            filetypes=[("FFmpeg", "ffmpeg.exe"), ("Todos", "*.*")],
            initialdir=os.path.dirname(self.ffmpeg_path) if self.ffmpeg_path else FFMPEG_DIR,
        )
        if not archivo:
            return

        self.ffmpeg_path = archivo
        ffprobe_same = os.path.join(os.path.dirname(archivo), "ffprobe.exe")
        if os.path.exists(ffprobe_same):
            self.ffprobe_path = ffprobe_same
            messagebox.showinfo("Actualizado", f"FFmpeg y FFProbe actualizados\n\n{archivo}")
        else:
            messagebox.showinfo("Actualizado", f"FFmpeg actualizado\n\n{archivo}\n\nSelecciona FFProbe manualmente si hace falta")
        self._actualizar_configuracion()

    def cambiar_ruta_ffprobe(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar ffprobe.exe",
            filetypes=[("FFProbe", "ffprobe.exe"), ("Todos", "*.*")],
            initialdir=os.path.dirname(self.ffprobe_path) if self.ffprobe_path else FFMPEG_DIR,
        )
        if archivo:
            self.ffprobe_path = archivo
            self._actualizar_configuracion()
            messagebox.showinfo("Actualizado", f"FFProbe actualizado\n\n{archivo}")

    def ver_info_ffmpeg(self):
        messagebox.showinfo(
            "Rutas configuradas",
            f"FFmpeg:\n{self.ffmpeg_path}\n\nFFProbe:\n{self.ffprobe_path}\n\nConfiguracion VPT:\n{CONFIG_DIR}",
        )

    def cambiar_preset(self):
        usar_nvidia = self.var_usar_nvidia.get()
        presets = PRESETS_NVIDIA if usar_nvidia else PRESETS_QSV
        gpu_name = "NVIDIA NVENC" if usar_nvidia else "Intel QSV"

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Preset - {gpu_name}")
        dialog.geometry("620x420")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text=f"Selecciona preset para {gpu_name}", font=("Segoe UI", 12, "bold")).pack(pady=10)

        # Ordenados manualmente de mas pesado (mejor calidad/mas lento) a mas liviano
        if usar_nvidia:
            orden_presets = ["lossless", "hq", "slow", "bd", "default", "medium", "llhq", "fast", "ll", "llhp", "hp"]
        else:
            orden_presets = ["veryslow", "slow", "medium", "fast", "faster", "veryfast"]

        options = []
        map_display = {}
        for key in orden_presets:
            if key not in presets:
                continue
            info = presets[key]
            disp = info["nombre"]
            options.append(disp)
            map_display[disp] = key

        current = self.preset_var.get()
        current = current if current in presets else obtener_preset_valido(current, usar_nvidia)
        value = tk.StringVar(value=presets[current]["nombre"])

        cb = ttk.Combobox(dialog, values=options, state="readonly", textvariable=value, width=44)
        cb.pack(pady=8)

        info_lbl = tk.Label(dialog, text="", justify=tk.LEFT, wraplength=560, anchor=tk.W)
        info_lbl.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def refresh(*_):
            selected = map_display.get(value.get())
            if not selected:
                return
            p = presets[selected]
            info_lbl.config(text=f"Nombre: {p['nombre']}\nVelocidad: {p['velocidad']}\nCalidad: {p['calidad']}\n\n{p['descripcion']}")

        value.trace_add("write", refresh)
        refresh()

        def aceptar():
            selected = map_display.get(value.get())
            if selected:
                self.preset_var.set(selected)
            dialog.destroy()

        btm = tk.Frame(dialog)
        btm.pack(pady=10)
        tk.Button(btm, text="Aceptar", command=aceptar, bg="#2D9CDB", fg="white", width=12).pack(side=tk.LEFT, padx=6)
        tk.Button(btm, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=12).pack(side=tk.LEFT, padx=6)

    def mostrar_acerca_de(self):
        txt = (
            "VPT Studio\n\n"
            "Fusiona funcionalidades de:\n"
            "1. Generacion de versiones Audio/Subtitulos\n"
            "2. Hardcode de subtitulos (NVENC/QSV)\n"
            "3. Limpieza de metadatos\n"
            "4. Verificacion estadistica de condiciones de streams\n\n"
            "Configuracion en: %APPDATA%/Galleon/VPT"
        )
        messagebox.showinfo("Acerca de", txt)

    def salir_aplicacion(self):
        if self.procesando and not messagebox.askyesno("Proceso activo", "Hay un proceso en curso. Salir de todos modos?"):
            return
        self._actualizar_configuracion()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = VPTSuite()
    app.run()
