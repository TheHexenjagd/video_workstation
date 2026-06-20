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

PRESETS_AMD = {
    "quality": {"nombre": "Quality", "descripcion": "Prioriza calidad", "velocidad": "⚡☆☆", "calidad": "★★★★★"},
    "balanced": {"nombre": "Balanced", "descripcion": "Balance entre velocidad y calidad", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "speed": {"nombre": "Speed", "descripcion": "Prioriza velocidad", "velocidad": "⚡⚡⚡⚡", "calidad": "★★☆☆"},
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
        "nombre_subcarpeta": "",
        "usar_nvidia": "True",
        "gpu_acel": "nvidia",
        "decod_hw": "Software",
        "preset": "medium",
        "sufijo_idiomas": "True",
        "limpiar_metadatos": "False",
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
        if stream.get("codec_type") != codec_type:
            continue
        tags = stream.get("tags", {})
        if tags.get("language", "und") == lang_buscado:
            return stream["index"]

    for stream in streams:
        if stream.get("codec_type") == codec_type:
            return stream["index"]

    return None


def obtener_preset_valido(preset, gpu_acel):
    if gpu_acel == "nvidia":
        if preset in PRESETS_NVIDIA:
            return preset
        mapeo = {
            "veryfast": "hp",
            "faster": "fast",
            "fast": "fast",
            "medium": "medium",
            "slow": "slow",
            "veryslow": "hq",
            "speed": "hp",
            "balanced": "medium",
            "quality": "hq",
        }
        return mapeo.get(preset, "default")

    elif gpu_acel == "intel":
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
            "speed": "veryfast",
            "balanced": "medium",
            "quality": "slow",
        }
        return mapeo.get(preset, "medium")

    elif gpu_acel == "amd":
        if preset in PRESETS_AMD:
            return preset
        mapeo = {
            "lossless": "quality",
            "hq": "quality",
            "slow": "quality",
            "bd": "quality",
            "default": "balanced",
            "medium": "balanced",
            "llhq": "balanced",
            "fast": "speed",
            "ll": "speed",
            "llhp": "speed",
            "hp": "speed",
            "veryslow": "quality",
            "faster": "speed",
            "veryfast": "speed",
        }
        return mapeo.get(preset, "balanced")

    return preset


class VPTSuite:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VPT Studio - Video Processing Toolkit")
        self.root.geometry("1220x820")
        self.root.minsize(1100, 740)

        self.gpus_status = {}
        self.gpu_availability = {}
        self.gpu_map_display_to_val = {
            "NVIDIA (NVENC)": "nvidia",
            "Intel (QSV)": "intel",
            "AMD (AMF)": "amd",
            "NVIDIA (NVENC) (No disponible)": "nvidia",
            "Intel (QSV) (No disponible)": "intel",
            "AMD (AMF) (No disponible)": "amd",
        }

        self.config_ini = self._cargar_configuracion()
        self.ffmpeg_path = self.config_ini.get("Paths", "ffmpeg", fallback=DEFAULT_CONFIG["Paths"]["ffmpeg"])
        self.ffprobe_path = self.config_ini.get("Paths", "ffprobe", fallback=DEFAULT_CONFIG["Paths"]["ffprobe"])

        self.msg_queue = queue.Queue()
        self.procesando = False
        self.cancelar_procesamiento = False
        self.proceso_actual = None
        self.nvenc_verificado = None

        self.pistas_config = {"audio_tag": None, "subtitle_tag": None, "aplicar_a_todos": False}
        self.combinaciones_a_aplicar = {"combinaciones": [], "aplicar_a_todos": False}

        self._crear_estilos()
        self._crear_menu()
        self._crear_ui()
        self._verificar_ffmpeg_inicio()
        self._iniciar_deteccion_gpus()

        self.root.protocol("WM_DELETE_WINDOW", self.salir_aplicacion)

    # -----------------------------
    # Configuracion
    # -----------------------------
    def _obtener_gpu_inicial(self):
        val = self.config_ini.get("Options", "gpu_acel", fallback=None)
        if val is None:
            usar_nvidia = self.config_ini.getboolean("Options", "usar_nvidia", fallback=True)
            val = "nvidia" if usar_nvidia else "intel"
        val = val.lower()
        if val not in ("nvidia", "intel", "amd"):
            val = "nvidia"
        return val

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
            if "Paths" not in self.config_ini:
                self.config_ini["Paths"] = {}
            self.config_ini["Paths"]["ffmpeg"] = self.ffmpeg_path
            self.config_ini["Paths"]["ffprobe"] = self.ffprobe_path
            self.config_ini["Paths"]["output_dir"] = self.salida_var.get()

            if "Options" not in self.config_ini:
                self.config_ini["Options"] = {}
            self.config_ini["Options"]["buscar_recursivo"] = str(self.var_recursivo.get())
            self.config_ini["Options"]["backup_original"] = str(self.var_backup.get())
            self.config_ini["Options"]["crear_subcarpeta"] = str(self.var_subcarpeta.get())
            self.config_ini["Options"]["nombre_subcarpeta"] = self.var_nombre_subcarpeta.get()
            self.config_ini["Options"]["gpu_acel"] = self.gpu_acel_var.get()
            self.config_ini["Options"]["decod_hw"] = self.decod_hw_var.get()
            self.config_ini["Options"]["usar_nvidia"] = str(self.gpu_acel_var.get() == "nvidia")
            self.config_ini["Options"]["preset"] = self.preset_var.get()
            self.config_ini["Options"]["sufijo_idiomas"] = str(self.var_sufijo_idiomas.get())
            self.config_ini["Options"]["limpiar_metadatos"] = str(self.var_limpiar_metadatos.get())

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
        self.var_recursivo = tk.BooleanVar(value=self.config_ini.getboolean("Options", "buscar_recursivo", fallback=True))
        self.var_backup = tk.BooleanVar(value=self.config_ini.getboolean("Options", "backup_original", fallback=True))
        self.var_subcarpeta = tk.BooleanVar(value=self.config_ini.getboolean("Options", "crear_subcarpeta", fallback=False))
        self.var_nombre_subcarpeta = tk.StringVar(value=self.config_ini.get("Options", "nombre_subcarpeta", fallback=""))
        self.gpu_acel_var = tk.StringVar(value=self._obtener_gpu_inicial())
        self.decod_hw_var = tk.StringVar(value=self.config_ini.get("Options", "decod_hw", fallback="Software"))
        self.preset_var = tk.StringVar(value=self.config_ini.get("Options", "preset", fallback="medium"))
        self.salida_var = tk.StringVar(value=self.config_ini.get("Paths", "output_dir", fallback=""))
        self.var_sufijo_idiomas = tk.BooleanVar(value=self.config_ini.getboolean("Options", "sufijo_idiomas", fallback=True))
        self.var_limpiar_metadatos = tk.BooleanVar(value=self.config_ini.getboolean("Options", "limpiar_metadatos", fallback=False))

        for var in [
            self.var_recursivo,
            self.var_backup,
            self.var_subcarpeta,
            self.var_nombre_subcarpeta,
            self.gpu_acel_var,
            self.decod_hw_var,
            self.preset_var,
            self.salida_var,
            self.var_sufijo_idiomas,
            self.var_limpiar_metadatos,
        ]:
            var.trace_add("write", self._actualizar_configuracion)

        main = ttk.Frame(self.root, style="VPT.TFrame")
        main.pack(fill=tk.BOTH, expand=True)

        hero = ttk.Frame(main, style="VPT.TFrame")
        hero.pack(fill=tk.X, padx=18, pady=(16, 10))
        
        title_frame = tk.Frame(hero, bg="#F3F7FF")
        title_frame.pack(anchor=tk.W)
        
        tk.Label(title_frame, text="VPT Studio", font=("Segoe UI", 22, "bold"), fg="#1F2A44", bg="#F3F7FF").pack(side=tk.LEFT)
        
        ttk.Label(hero, text="Herramienta de procesamiento de vídeo, codificación por hardware y multiplexación", style="SubHeader.TLabel").pack(anchor=tk.W, pady=(4, 0))

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
        tk.Checkbutton(acciones, text="Buscar recursivo", variable=self.var_recursivo, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=8)

        right = ttk.Frame(top, style="Card.TFrame")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=4)

        ttk.Label(right, text="Modulos", style="CardTitle.TLabel").pack(anchor=tk.W, padx=12, pady=(10, 6))
        
        # Modern custom tab header
        self.tab_header = tk.Frame(right, bg="#FFFFFF")
        self.tab_header.pack(fill=tk.X, padx=12, pady=(0, 2))

        # Underline separator for the tab header
        tab_divider = tk.Frame(right, height=1, bg="#E5ECF9")
        tab_divider.pack(fill=tk.X, padx=12, pady=(0, 10))

        self.tab_content_container = ttk.Frame(right, style="Card.TFrame")
        self.tab_content_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))
        self.tab_content_container.grid_rowconfigure(0, weight=1)
        self.tab_content_container.grid_columnconfigure(0, weight=1)

        self.tab_asrt = ttk.Frame(self.tab_content_container, style="Card.TFrame")
        self.tab_hst = ttk.Frame(self.tab_content_container, style="Card.TFrame")
        self.tab_tools = ttk.Frame(self.tab_content_container, style="Card.TFrame")

        self.tab_asrt.grid(row=0, column=0, sticky="nsew")
        self.tab_hst.grid(row=0, column=0, sticky="nsew")
        self.tab_tools.grid(row=0, column=0, sticky="nsew")

        self.tab_frames = [self.tab_asrt, self.tab_hst, self.tab_tools]
        self.tab_labels_text = ["Versiones Audio/Sub", "Hardcode", "Mantenimiento"]
        self.tab_buttons = []
        self.tab_indicators = []
        self.tab_label_widgets = []

        for i, text in enumerate(self.tab_labels_text):
            btn_frame = tk.Frame(self.tab_header, bg="#FFFFFF", cursor="hand2")
            btn_frame.pack(side=tk.LEFT, padx=(0, 16))

            lbl = tk.Label(btn_frame, text=text, font=("Segoe UI", 10, "bold"), bg="#FFFFFF", fg="#5C6B8A", pady=6)
            lbl.pack(fill=tk.X)

            ind = tk.Frame(btn_frame, height=3, bg="#FFFFFF")
            ind.pack(fill=tk.X)

            lbl.bind("<Button-1>", lambda e, idx=i: self._seleccionar_pestana(idx))
            btn_frame.bind("<Button-1>", lambda e, idx=i: self._seleccionar_pestana(idx))

            self.tab_buttons.append(btn_frame)
            self.tab_label_widgets.append(lbl)
            self.tab_indicators.append(ind)

        self._crear_tab_asrt()
        self._crear_tab_hst()
        self._crear_tab_tools()
        
        self._seleccionar_pestana(0)

        base = ttk.Frame(main, style="Card.TFrame")
        base.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 14))

        # 1. Directorio de Salida
        salida_frame = tk.Frame(base, bg="#FFFFFF")
        salida_frame.pack(fill=tk.X, padx=12, pady=(12, 6))
        tk.Label(salida_frame, text="1. Directorio de Salida:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        tk.Entry(salida_frame, textvariable=self.salida_var, bg="#F4F8FF", fg="#1F2A44", relief=tk.FLAT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self._btn(salida_frame, "Seleccionar", self.seleccionar_directorio, "#4DA8DA").pack(side=tk.LEFT)

        # 2. Estructura de Subcarpetas
        subcarp_frame = tk.Frame(base, bg="#FFFFFF")
        subcarp_frame.pack(fill=tk.X, padx=12, pady=6)
        tk.Label(subcarp_frame, text="2. Estructura de Subcarpeta:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        tk.Checkbutton(subcarp_frame, text="Crear subcarpeta", variable=self.var_subcarpeta, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=(0, 8))
        
        try:
            presets_data = json.loads(self.config_ini.get("Options", "presets", fallback='[]'))
        except Exception:
            presets_data = []
        self.cb_nombre_subcarpeta = ttk.Combobox(subcarp_frame, textvariable=self.var_nombre_subcarpeta, values=presets_data, width=32)
        self.cb_nombre_subcarpeta.pack(side=tk.LEFT, padx=(0, 6))
        
        btn_build = tk.Button(
            subcarp_frame,
            text="Configurar",
            command=self._abrir_constructor_rutas,
            bg="#2D9CDB",
            fg="white",
            activebackground="#2D9CDB",
            activeforeground="white",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        btn_build.pack(side=tk.LEFT)

        # 3. Opciones Generales
        opts_frame = tk.Frame(base, bg="#FFFFFF")
        opts_frame.pack(fill=tk.X, padx=12, pady=(6, 12))
        tk.Label(opts_frame, text="3. Opciones Generales:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        tk.Checkbutton(opts_frame, text="Backup original", variable=self.var_backup, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=8)
        
        tk.Label(opts_frame, text="GPU:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(8, 4))
        self.cb_gpu = ttk.Combobox(opts_frame, values=["NVIDIA (NVENC)", "Intel (QSV)", "AMD (AMF)"], state="readonly", width=16)
        self.cb_gpu.pack(side=tk.LEFT, padx=4)
        self.cb_gpu.bind("<<ComboboxSelected>>", self._on_gpu_selected)

        tk.Label(opts_frame, text="Decodificación:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(8, 4))
        self.cb_decod = ttk.Combobox(opts_frame, values=["Software", "D3D11VA", "DXVA2"], state="readonly", textvariable=self.decod_hw_var, width=10)
        self.cb_decod.pack(side=tk.LEFT, padx=4)
        
        tk.Checkbutton(opts_frame, text="Añadir sufijo al nombre", variable=self.var_sufijo_idiomas, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=8)
        tk.Checkbutton(opts_frame, text="Limpiar metadatos al finalizar", variable=self.var_limpiar_metadatos, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=8)

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

    def _seleccionar_pestana(self, index):
        for i, (frm, lbl, ind) in enumerate(zip(self.tab_frames, self.tab_label_widgets, self.tab_indicators)):
            if i == index:
                frm.tkraise()
                lbl.config(fg="#2D9CDB")
                ind.config(bg="#2D9CDB")
            else:
                lbl.config(fg="#5C6B8A")
                ind.config(bg="#FFFFFF")

    def _crear_tab_asrt(self):
        frm = tk.Frame(self.tab_asrt, bg="#FFFFFF")
        frm.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        tk.Label(frm, text="Genera multiples versiones por combinaciones de audio/subtitulos", bg="#FFFFFF", fg="#5C6B8A", font=("Segoe UI", 10)).pack(anchor=tk.W)
        btns = tk.Frame(frm, bg="#FFFFFF")
        btns.pack(anchor=tk.W, pady=12)
        self.btn_versiones = self._btn(btns, "Generar versiones", self.procesar_versiones, "#2D9CDB")
        self.btn_versiones.pack(side=tk.LEFT, padx=(0, 8))
        self._btn(btns, "Verificar condiciones", self.verificar_condiciones_carpeta, "#27AE60").pack(side=tk.LEFT, padx=(0, 8))
        self.btn_cancelar_asrt = self._btn(btns, "Cancelar todo", self.cancelar, "#EB5757")
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
        self.btn_cancelar_hst = self._btn(btns, "Cancelar todo", self.cancelar, "#EB5757")
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
        self.btn_cancelar = self._btn(btns, "Cancelar todo", self.cancelar, "#EB5757")
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
            self._enviar_mensaje(f"Error ffprobe: {result.stderr[:220]}")
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
        nuevo = obtener_preset_valido(preset_actual, self.gpu_acel_var.get())
        if nuevo != preset_actual:
            self.preset_var.set(nuevo)

    def _nvidia_disponible(self):
        return self._check_encoder("h264_nvenc")

    def _check_encoder(self, encoder):
        if not os.path.exists(self.ffmpeg_path):
            return False, "FFmpeg no encontrado"

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # 1. Quick check in -encoders output
            encoders_proc = subprocess.run(
                [self.ffmpeg_path, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=5
            )
            if encoders_proc.returncode != 0 or encoder not in encoders_proc.stdout:
                return False, "No soportado por FFmpeg"
                
            # 2. Test execution to see if hardware initializes
            test_proc = subprocess.run(
                [
                    self.ffmpeg_path,
                    "-hide_banner",
                    "-f",
                    "lavfi",
                    "-i",
                    "nullsrc=s=256x256:d=1",
                    "-c:v",
                    encoder,
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=5
            )
            if test_proc.returncode != 0:
                err_msg = test_proc.stderr.strip().split("\n")[-1] if test_proc.stderr else "Driver o GPU no disponible"
                return False, err_msg
            return True, "Disponible"
        except Exception as exc:
            return False, f"Error: {exc}"

    def _iniciar_deteccion_gpus(self):
        self._enviar_mensaje("Iniciando detección de hardware gráfico...")
        threading.Thread(target=self._detectar_gpus_thread, daemon=True).start()

    def _detectar_gpus_thread(self):
        nv_ok, nv_msg = self._check_encoder("h264_nvenc")
        intel_ok, intel_msg = self._check_encoder("h264_qsv")
        amd_ok, amd_msg = self._check_encoder("h264_amf")

        self.gpus_status = {
            "nvidia": (nv_ok, nv_msg),
            "intel": (intel_ok, intel_msg),
            "amd": (amd_ok, amd_msg)
        }
        
        self._enviar_mensaje(f"Detección GPU - NVIDIA NVENC: {'OK' if nv_ok else 'No disponible (' + nv_msg + ')'}")
        self._enviar_mensaje(f"Detección GPU - Intel QSV: {'OK' if intel_ok else 'No disponible (' + intel_msg + ')'}")
        self._enviar_mensaje(f"Detección GPU - AMD AMF: {'OK' if amd_ok else 'No disponible (' + amd_msg + ')'}")

        self.root.after(0, self._actualizar_selector_gpus_ui)

    def _actualizar_selector_gpus_ui(self):
        values = []
        self.gpu_availability = {}
        for gpu_key, display_name in [("nvidia", "NVIDIA (NVENC)"), ("intel", "Intel (QSV)"), ("amd", "AMD (AMF)")]:
            is_ok = self.gpus_status.get(gpu_key, (False, ""))[0]
            self.gpu_availability[gpu_key] = is_ok
            if is_ok:
                lbl = display_name
            else:
                lbl = f"{display_name} (No disponible)"
            values.append(lbl)
            self.gpu_map_display_to_val[lbl] = gpu_key

        self.cb_gpu.config(values=values)
        self._sincronizar_combobox_con_variable()

    def _sincronizar_combobox_con_variable(self):
        current_val = self.gpu_acel_var.get()
        for lbl in self.cb_gpu["values"]:
            if self.gpu_map_display_to_val.get(lbl) == current_val:
                self.cb_gpu.set(lbl)
                break

    def _on_gpu_selected(self, event=None):
        selected_lbl = self.cb_gpu.get()
        gpu_key = self.gpu_map_display_to_val.get(selected_lbl)
        
        is_ok = self.gpu_availability.get(gpu_key, True)
        if not is_ok:
            status = self.gpus_status.get(gpu_key, (False, "No disponible"))
            messagebox.showwarning(
                "Codificador no disponible",
                f"El codificador seleccionado ({selected_lbl}) no está disponible o no se pudo inicializar en su sistema.\nDetalle: {status[1]}\n\nSe restablecerá la selección anterior.",
                parent=self.root
            )
            self._sincronizar_combobox_con_variable()
            return
            
        self.gpu_acel_var.set(gpu_key)
        self._on_gpu_change()

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
        if not resultado["ok"]:
            ans = messagebox.askyesnocancel(
                "Cancelar proceso",
                "¿Deseas cancelar todo el procesamiento?\n\n"
                "Sí: Cancela toda la cola de videos.\n"
                "No: Salta este archivo y continúa con el siguiente.\n"
                "Cancelar: Vuelve a la selección de pistas.",
                parent=self.root
            )
            if ans is True:
                self.cancelar_procesamiento = True
                resultado["ok"] = False
            elif ans is False:
                resultado["ok"] = False
            else:
                return self._mostrar_selector_pistas(info, filename)
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
            var.trace_add("write", lambda *_: actualizar_estado_hardsub())
            audio_vars.append((var, s))
            tk.Checkbutton(left, text=f"{title} ({lang})", variable=var, anchor=tk.W).pack(fill=tk.X, padx=8, pady=2)

        tk.Label(left, text="Subtitulos", fg="#2980B9", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=6, pady=(8, 2))
        sub_vars = []
        for i, s in enumerate(subtitle_streams):
            tags = s.get("tags", {})
            title = tags.get("title") or f"Sub {i + 1}"
            lang = tags.get("language", "und")
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_: actualizar_estado_hardsub())
            sub_vars.append((var, s))
            tk.Checkbutton(left, text=f"{title} ({lang})", variable=var, anchor=tk.W).pack(fill=tk.X, padx=8, pady=2)

        var_hardsub = tk.BooleanVar(value=False)
        cb_hardsub = tk.Checkbutton(left, text="Hacer hardsub (Incrustar)", variable=var_hardsub, font=("Segoe UI", 9, "bold"), fg="#E74C3C", activeforeground="#E74C3C", state=tk.DISABLED)
        cb_hardsub.pack(anchor=tk.W, padx=8, pady=12)

        def actualizar_estado_hardsub():
            aud_sel = [s for v, s in audio_vars if v.get()]
            sub_sel = [s for v, s in sub_vars if v.get()]
            if len(aud_sel) == 1 and len(sub_sel) == 1:
                cb_hardsub.config(state=tk.NORMAL)
            else:
                var_hardsub.set(False)
                cb_hardsub.config(state=tk.DISABLED)

        right = tk.LabelFrame(body, text="Versiones")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        lst = tk.Listbox(right, font=("Consolas", 9))
        lst.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        def refresh():
            lst.delete(0, tk.END)
            for i, combo in enumerate(combinaciones):
                suffix = " (Hardsub)" if combo.get("hardsub") else ""
                lst.insert(tk.END, f"{i + 1}. {combo['label']}{suffix}")

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
                    "hardsub": var_hardsub.get(),
                }
            )
            refresh()
            for var, _ in audio_vars:
                var.set(False)
            for var, _ in sub_vars:
                var.set(False)
            var_hardsub.set(False)

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
        if not resultado["ok"]:
            ans = messagebox.askyesnocancel(
                "Cancelar proceso",
                "¿Deseas cancelar todo el procesamiento?\n\n"
                "Sí: Cancela toda la cola de videos.\n"
                "No: Salta este archivo y continúa con el siguiente.\n"
                "Cancelar: Vuelve a la selección de pistas.",
                parent=self.root
            )
            if ans is True:
                self.cancelar_procesamiento = True
                resultado["ok"] = False
            elif ans is False:
                resultado["ok"] = False
            else:
                return self._mostrar_selector_combinaciones(info, filename)
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
                            "hardsub": c.get("hardsub", False),
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
                        "hardsub": c.get("hardsub", False),
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
            if self.cancelar_procesamiento:
                break
            audio_indices = combo.get("audio_indices", [])
            sub_indices = combo.get("sub_indices", [])
            label = combo.get("label", "VERSION")

            # Resolve output directory and output path common to both branches
            out_dir = Path(output_dir)
            if self.var_subcarpeta.get():
                patron = self._resolver_patron_subcarpeta(input_file, info, label, audio_indices, sub_indices)
                out_dir = out_dir / Path(patron)

            out_dir.mkdir(parents=True, exist_ok=True)
            suffix = f"_{label}" if self.var_sufijo_idiomas.get() else ""
            output_path = out_dir / f"{video_stem}{suffix}.mp4"

            if combo.get("hardsub"):
                gpu = self.gpu_acel_var.get()
                is_ok = self.gpu_availability.get(gpu, True)
                if not is_ok:
                    status = self.gpus_status.get(gpu, (False, "No disponible"))
                    self._enviar_mensaje(f"Error: El codificador {gpu.upper()} no está disponible. Detalle: {status[1]}. Saltando hardsub.")
                    fail += 1
                    continue

                audio_idx = audio_indices[0] if audio_indices else None
                sub_idx = sub_indices[0] if sub_indices else None
                temp_subtitle_path = None
                
                try:
                    if sub_idx is not None:
                        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False, encoding="utf-8")
                        temp_subtitle_path = tf.name
                        tf.close()
                        
                        extract = [self.ffmpeg_path, "-i", input_file, "-map", f"0:{sub_idx}", "-y", temp_subtitle_path]
                        res = self._run_subprocess_cancellable(extract)
                        if res.returncode != 0:
                            fail += 1
                            continue
                            
                        esc = temp_subtitle_path.replace("\\", "/").replace(":", "\\:")
                        video_filter = f"ass='{esc}',format=yuv420p"
                    else:
                        video_filter = "format=yuv420p"
                        
                    audio_codec = None
                    for s in info["streams"]:
                        if s.get("codec_type") == "audio" and s.get("index") == audio_idx:
                            audio_codec = s.get("codec_name")
                            break
                    audio_settings = ["-c:a", "aac", "-b:a", "320k"] if audio_codec == "flac" else ["-c:a", "copy"]
                    
                    preset = obtener_preset_valido(self.preset_var.get(), self.gpu_acel_var.get())
                    
                    decod_val = self.decod_hw_var.get().lower()
                    hwaccel_opts = []
                    if decod_val in ("d3d11va", "dxva2"):
                        hwaccel_opts = ["-hwaccel", decod_val]

                    if gpu == "nvidia":
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_nvenc", "-preset", preset,
                            "-profile:v", "high", "-rc", "vbr_hq", "-cq", "23",
                            "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *audio_settings, "-movflags", "+faststart", "-y", str(output_path)
                        ]
                    elif gpu == "intel":
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_qsv", "-preset", preset,
                            "-global_quality", "23",
                            "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *audio_settings, "-movflags", "+faststart", "-y", str(output_path)
                        ]
                    else:  # amd
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_amf", "-quality", preset,
                            "-rc", "vbr_peak", "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *audio_settings, "-movflags", "+faststart", "-y", str(output_path)
                        ]
                    
                    self._enviar_mensaje(f"[{i}/{len(combinaciones)}] {output_path.name} (Incrustando subtítulos...)")
                    result = self._run_subprocess_cancellable(cmd)
                    if result.returncode == 0:
                        ok += 1
                        aud_langs = []
                        for idx in audio_indices:
                            s = next((st for st in info["streams"] if st.get("index") == idx), None)
                            if s:
                                lang = s.get("tags", {}).get("language", "und")
                                title = s.get("tags", {}).get("title", "")
                                codec = s.get("codec_name", "")
                                aud_langs.append(f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})")
                        
                        sub_langs = []
                        sub_list = [sub_idx] if sub_idx is not None else []
                        for idx in sub_list:
                            s = next((st for st in info["streams"] if st.get("index") == idx), None)
                            if s:
                                lang = s.get("tags", {}).get("language", "und")
                                title = s.get("tags", {}).get("title", "")
                                codec = s.get("codec_name", "")
                                sub_langs.append(f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})")
                        
                        ruta_completa = os.path.abspath(output_path)
                        audios_info = ", ".join(aud_langs) if aud_langs else "Ninguno"
                        subs_info = ", ".join(sub_langs) if sub_langs else "Ninguno"
                        self._enviar_mensaje(f"  -> Archivo generado: {ruta_completa}")
                        self._enviar_mensaje(f"     Audios: {audios_info}")
                        self._enviar_mensaje(f"     Subtítulos: {subs_info}")

                        if self.var_limpiar_metadatos.get():
                            self._enviar_mensaje(f"Limpiando metadatos de {output_path.name}...")
                            self._limpiar_metadatos_archivo(output_path)
                    else:
                        fail += 1
                        self._enviar_mensaje("Error al generar version hardsub")
                finally:
                    if temp_subtitle_path and os.path.exists(temp_subtitle_path):
                        try:
                            os.unlink(temp_subtitle_path)
                        except Exception:
                            pass
            else:
                sub_incluir = []
                excluidos = 0
                for idx in sub_indices:
                    s = next((st for st in subtitle_streams if st["index"] == idx), None)
                    if s and s.get("codec_name", "").lower() in BITMAP_SUB_CODECS:
                        excluidos += 1
                    else:
                        sub_incluir.append(idx)

                if excluidos:
                    self._enviar_mensaje(f"Advertencia: {excluidos} subtitulos bitmap excluidos")

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

                self._enviar_mensaje(f"[{i}/{len(combinaciones)}] {output_path.name}")
                result = self._run_subprocess_cancellable(cmd)
                if result.returncode == 0:
                    ok += 1
                    aud_langs = []
                    for idx in audio_indices:
                        s = next((st for st in info["streams"] if st.get("index") == idx), None)
                        if s:
                            lang = s.get("tags", {}).get("language", "und")
                            title = s.get("tags", {}).get("title", "")
                            codec = s.get("codec_name", "")
                            aud_langs.append(f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})")
                    
                    sub_langs = []
                    for idx in sub_incluir:
                        s = next((st for st in info["streams"] if st.get("index") == idx), None)
                        if s:
                            lang = s.get("tags", {}).get("language", "und")
                            title = s.get("tags", {}).get("title", "")
                            codec = s.get("codec_name", "")
                            sub_langs.append(f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})")
                    
                    ruta_completa = os.path.abspath(output_path)
                    audios_info = ", ".join(aud_langs) if aud_langs else "Ninguno"
                    subs_info = ", ".join(sub_langs) if sub_langs else "Ninguno"
                    self._enviar_mensaje(f"  -> Archivo generado: {ruta_completa}")
                    self._enviar_mensaje(f"     Audios: {audios_info}")
                    self._enviar_mensaje(f"     Subtítulos: {subs_info}")

                    if self.var_limpiar_metadatos.get():
                        self._enviar_mensaje(f"Limpiando metadatos de {output_path.name}...")
                        self._limpiar_metadatos_archivo(output_path)
                else:
                    fail += 1
                    self._enviar_mensaje("Error al generar version")

        return ok, fail

    def _eliminar_pistas_versiones(self, archivo, output_dir):
        info = self._ffprobe_info(archivo)
        if info is None:
            self._enviar_mensaje("No se pudo leer streams")
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
                self._enviar_mensaje("Cancelado por usuario")
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
        sufijo = ""
        if self.var_sufijo_idiomas.get():
            sufijo = "_hardcoded" if sub_idx is not None else "_nosub"

        if self.var_subcarpeta.get():
            sub_indices = [sub_idx] if sub_idx is not None else []
            patron = self._resolver_patron_subcarpeta(input_file, info, sufijo.strip("_") or "hardcode", [audio_idx], sub_indices)
            out_dir = out_dir / Path(patron)

        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{Path(input_file).stem}{sufijo}.mp4"

        temp_subtitle_path = None

        try:
            if sub_idx is not None:
                tf = tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False, encoding="utf-8")
                temp_subtitle_path = tf.name
                tf.close()

                extract = [self.ffmpeg_path, "-i", input_file, "-map", f"0:{sub_idx}", "-y", temp_subtitle_path]
                res = self._run_subprocess_cancellable(extract)
                if res.returncode != 0:
                    return False

                esc = temp_subtitle_path.replace("\\", "/").replace(":", "\\:")
                video_filter = f"ass='{esc}',format=yuv420p"
            else:
                video_filter = "format=yuv420p"

            preset = obtener_preset_valido(self.preset_var.get(), self.gpu_acel_var.get())

            decod_val = self.decod_hw_var.get().lower()
            hwaccel_opts = []
            if decod_val in ("d3d11va", "dxva2"):
                hwaccel_opts = ["-hwaccel", decod_val]

            gpu = self.gpu_acel_var.get()

            if gpu == "nvidia":
                cmd = [
                    self.ffmpeg_path,
                    *hwaccel_opts,
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
            elif gpu == "intel":
                cmd = [
                    self.ffmpeg_path,
                    *hwaccel_opts,
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
            else:  # amd
                cmd = [
                    self.ffmpeg_path,
                    *hwaccel_opts,
                    "-i",
                    input_file,
                    "-map",
                    "0:v:0",
                    "-map",
                    f"0:{audio_idx}",
                    "-vf",
                    video_filter,
                    "-c:v",
                    "h264_amf",
                    "-quality",
                    preset,
                    "-rc",
                    "vbr_peak",
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

            res = self._run_subprocess_cancellable(cmd)
            if res.returncode == 0:
                s_aud = next((st for st in info["streams"] if st.get("index") == audio_idx), None)
                if s_aud:
                    lang = s_aud.get("tags", {}).get("language", "und")
                    title = s_aud.get("tags", {}).get("title", "")
                    codec = s_aud.get("codec_name", "")
                    audio_info = f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})"
                else:
                    audio_info = "Desconocido"

                if sub_idx is not None:
                    s_sub = next((st for st in info["streams"] if st.get("index") == sub_idx), None)
                    if s_sub:
                        lang = s_sub.get("tags", {}).get("language", "und")
                        title = s_sub.get("tags", {}).get("title", "")
                        codec = s_sub.get("codec_name", "")
                        sub_info = f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})"
                    else:
                        sub_info = "Desconocido"
                else:
                    sub_info = "Ninguno"

                ruta_completa = os.path.abspath(out_file)
                self._enviar_mensaje(f"  -> Archivo generado: {ruta_completa}")
                self._enviar_mensaje(f"     Audio: {audio_info}")
                self._enviar_mensaje(f"     Subtítulo (Incrustado): {sub_info}")

                if self.var_limpiar_metadatos.get():
                    self._enviar_mensaje(f"Limpiando metadatos de {out_file.name}...")
                    self._limpiar_metadatos_archivo(out_file)
                return True
            return False

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

        gpu = self.gpu_acel_var.get()
        is_ok = self.gpu_availability.get(gpu, True)
        if not is_ok:
            status = self.gpus_status.get(gpu, (False, "No disponible"))
            self._enviar_mensaje(f"Error: El codificador {gpu.upper()} no está disponible. Detalle: {status[1]}")
            self.msg_queue.put(("FINALIZADO", 0, total))
            self.procesando = False
            return

        self._enviar_mensaje("===== INICIO HARDCODE =====")
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._enviar_mensaje("Cancelado por usuario")
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
            res = self._run_subprocess_cancellable(cmd, stdout_devnull=True)
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
                self._enviar_mensaje("Cancelado por usuario")
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

    def _resolver_patron_subcarpeta(self, filepath, info, label, audio_indices, sub_indices):
        video_stem = Path(filepath).stem
        parent_folder = Path(filepath).parent.name or "input_folder"
        if info is None:
            patron = self.var_nombre_subcarpeta.get().strip()
            patron = patron.replace("{name}", video_stem)
            patron = patron.replace("{folder}", parent_folder)
            patron = patron.replace("{label}", label)
            patron = patron.replace("{audio_langs}", "UND")
            patron = patron.replace("{sub_langs}", "NONE")
            patron = patron.replace("{codec_v}", "unknown")
            patron = patron.replace("{codec_a}", "unknown")
            patron = patron.replace("{resolution}", "unknown")
            return patron

        video_stream = next((s for s in info["streams"] if s.get("codec_type") == "video"), {})
        codec_v = video_stream.get("codec_name", "unknown")
        
        try:
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
        except (ValueError, TypeError):
            width = 0
            height = 0

        if height >= 2160 or width >= 3840:
            resolution = "2160p"
        elif height >= 1080 or width >= 1920:
            resolution = "1080p"
        elif height >= 720 or width >= 1280:
            resolution = "720p"
        elif height >= 480 or width >= 854:
            resolution = "480p"
        elif height > 0:
            resolution = f"{height}p"
        else:
            resolution = "unknown"

        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        if audio_indices:
            selected_audios = [s for s in audio_streams if s.get("index") in audio_indices]
        else:
            selected_audios = audio_streams[:1] if audio_streams else []

        codec_a = selected_audios[0].get("codec_name", "unknown") if selected_audios else "none"

        audio_langs = []
        for s in (selected_audios if audio_indices else audio_streams):
            lang = s.get("tags", {}).get("language", "und").upper()
            if lang not in audio_langs:
                audio_langs.append(lang)
        audio_langs_str = "_".join(audio_langs) if audio_langs else "UND"

        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
        if sub_indices:
            sub_indices_ints = [int(x) for x in sub_indices if x is not None]
            selected_subs = [s for s in subtitle_streams if int(s.get("index", -1)) in sub_indices_ints]
        else:
            selected_subs = []

        sub_langs = []
        for s in selected_subs:
            lang = s.get("tags", {}).get("language", "und").upper()
            if lang not in sub_langs:
                sub_langs.append(lang)
        sub_langs_str = "_".join(sub_langs) if sub_langs else "NONE"

        patron = self.var_nombre_subcarpeta.get().strip()
        
        mapping = {
            "{name}": video_stem,
            "{folder}": parent_folder,
            "{label}": label,
            "{audio_langs}": audio_langs_str,
            "{sub_langs}": sub_langs_str,
            "{codec_v}": codec_v,
            "{codec_a}": codec_a,
            "{resolution}": resolution
        }
        
        for placeholder, val in mapping.items():
            patron = patron.replace(placeholder, str(val))
            
        return patron

    def _abrir_constructor_rutas(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Constructor de Ruta de Salida")
        dialog.geometry("680x520")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#F3F7FF")

        tk.Label(dialog, text="Constructor de Ruta de Salida", font=("Segoe UI", 12, "bold"), bg="#F3F7FF", fg="#1F2A44").pack(pady=(12, 6))
        tk.Label(dialog, text="Haz clic en las banderas para agregarlas al patrón de subcarpeta:", font=("Segoe UI", 9), bg="#F3F7FF", fg="#5C6B8A").pack(pady=(0, 10))

        patron_var = tk.StringVar(value=self.var_nombre_subcarpeta.get())
        entry = tk.Entry(dialog, textvariable=patron_var, font=("Consolas", 11), bg="#FFFFFF", fg="#1F2A44", relief=tk.SOLID, bd=1)
        entry.pack(fill=tk.X, padx=20, pady=8)
        entry.focus_set()

        # Presets Row
        presets_frame = tk.Frame(dialog, bg="#F3F7FF")
        presets_frame.pack(fill=tk.X, padx=20, pady=(4, 8))
        
        tk.Label(presets_frame, text="Presets:", font=("Segoe UI", 9, "bold"), bg="#F3F7FF", fg="#2B3A57").pack(side=tk.LEFT, padx=(0, 6))
        
        try:
            presets_data = json.loads(self.config_ini.get("Options", "presets", fallback='[]'))
        except Exception:
            presets_data = []
        
        presets_var = tk.StringVar()
        cb_presets = ttk.Combobox(presets_frame, values=presets_data, textvariable=presets_var, state="readonly", width=40)
        cb_presets.pack(side=tk.LEFT, padx=6)
        if presets_data:
            presets_var.set(presets_data[0])
        
        def on_preset_selected(*_):
            selected = presets_var.get()
            if selected:
                patron_var.set(selected)
                
        cb_presets.bind("<<ComboboxSelected>>", on_preset_selected)

        def guardar_nuevo_preset():
            nuevo = patron_var.get().strip()
            if not nuevo:
                return
            try:
                curr = json.loads(self.config_ini.get("Options", "presets", fallback='[]'))
            except Exception:
                curr = []
                
            if nuevo not in curr:
                curr.append(nuevo)
                if "Options" not in self.config_ini:
                    self.config_ini["Options"] = {}
                self.config_ini["Options"]["presets"] = json.dumps(curr)
                self._guardar_configuracion()
                self.cb_nombre_subcarpeta["values"] = curr
                cb_presets["values"] = curr
                presets_var.set(nuevo)
                messagebox.showinfo("Preset Guardado", f"Se ha guardado el preset:\n{nuevo}", parent=dialog)
        
        btn_add_preset = tk.Button(
            presets_frame,
            text="Guardar actual",
            command=guardar_nuevo_preset,
            bg="#27AE60",
            fg="white",
            activebackground="#27AE60",
            activeforeground="white",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_add_preset.pack(side=tk.LEFT, padx=6)

        def eliminar_preset_seleccionado():
            seleccionado = cb_presets.get()
            if not seleccionado:
                return
            try:
                curr = json.loads(self.config_ini.get("Options", "presets", fallback='[]'))
            except Exception:
                curr = []
                
            if seleccionado in curr:
                curr.remove(seleccionado)
                if "Options" not in self.config_ini:
                    self.config_ini["Options"] = {}
                self.config_ini["Options"]["presets"] = json.dumps(curr)
                self._guardar_configuracion()
                self.cb_nombre_subcarpeta["values"] = curr
                cb_presets["values"] = curr
                if curr:
                    presets_var.set(curr[0])
                    patron_var.set(curr[0])
                else:
                    presets_var.set("")
                    patron_var.set("")
                messagebox.showinfo("Preset Eliminado", "El preset seleccionado ha sido eliminado.", parent=dialog)
                
        btn_del_preset = tk.Button(
            presets_frame,
            text="Eliminar",
            command=eliminar_preset_seleccionado,
            bg="#EB5757",
            fg="white",
            activebackground="#EB5757",
            activeforeground="white",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_del_preset.pack(side=tk.LEFT, padx=6)

        flags_frame = tk.LabelFrame(dialog, text="Banderas Disponibles", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57", padx=10, pady=10)
        flags_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        flags_frame.configure(relief=tk.GROOVE)

        flags = [
            ("{name}", "Nombre original del video"),
            ("{folder}", "Nombre de la carpeta contenedora del video"),
            ("{label}", "Etiqueta/Versión (ej: ESP_subENG, hardcoded)"),
            ("{audio_langs}", "Idiomas de audio resultantes (ej: ESP_ENG)"),
            ("{sub_langs}", "Idiomas de subtítulos resultantes (ej: SPA, NONE)"),
            ("{codec_v}", "Codec de video (ej: h264, hevc)"),
            ("{codec_a}", "Codec de audio (ej: aac, ac3)"),
            ("{resolution}", "Resolución del video (ej: 1080p, 720p)"),
        ]

        def insertar_flag(flag):
            pos = entry.index(tk.INSERT)
            entry.insert(pos, flag)
            entry.focus_set()
            actualizar_preview()

        for i, (flag, desc) in enumerate(flags):
            row = tk.Frame(flags_frame, bg="#FFFFFF")
            row.pack(fill=tk.X, pady=3)
            
            btn = tk.Button(
                row,
                text=flag,
                command=lambda f=flag: insertar_flag(f),
                bg="#2D9CDB",
                fg="white",
                activebackground="#2D9CDB",
                activeforeground="white",
                relief=tk.FLAT,
                width=16,
                font=("Consolas", 9, "bold"),
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=(0, 10))
            
            tk.Label(row, text=desc, font=("Segoe UI", 9), bg="#FFFFFF", fg="#5C6B8A").pack(side=tk.LEFT)

        preview_frame = tk.Frame(dialog, bg="#E5ECF9", padx=10, pady=10)
        btm = tk.Frame(dialog, bg="#F3F7FF")

        # Pack bottom elements first to ensure visibility
        btm.pack(side=tk.BOTTOM, pady=(5, 12))
        preview_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=10)
        flags_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(preview_frame, text="Vista previa de ruta resuelta:", font=("Segoe UI", 9, "bold"), bg="#E5ECF9", fg="#2B3A57").pack(anchor=tk.W)
        preview_lbl = tk.Label(preview_frame, text="", font=("Consolas", 9), bg="#E5ECF9", fg="#1F2A44", wraplength=620, justify=tk.LEFT)
        preview_lbl.pack(anchor=tk.W, pady=(4, 0))

        def actualizar_preview(*_):
            archivos = list(self.lista.get(0, tk.END))
            patron = patron_var.get()
            
            dummy_info = {
                "streams": [
                    {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "index": 0},
                    {"codec_type": "audio", "codec_name": "ac3", "index": 1, "tags": {"language": "spa"}},
                    {"codec_type": "audio", "codec_name": "aac", "index": 2, "tags": {"language": "eng"}},
                    {"codec_type": "subtitle", "codec_name": "subrip", "index": 3, "tags": {"language": "eng"}}
                ]
            }
            
            video_name = "Ejemplo_Video"
            info = dummy_info
            audio_indices = [1, 2]
            sub_indices = [3]
            
            if archivos:
                video_name = Path(archivos[0]).stem
                real_info = self._ffprobe_info(archivos[0])
                if real_info:
                    info = real_info
                    audio_indices = [s["index"] for s in info["streams"] if s.get("codec_type") == "audio"]
                    sub_indices = [s["index"] for s in info["streams"] if s.get("codec_type") == "subtitle"]

            old_val = self.var_nombre_subcarpeta.get()
            self.var_nombre_subcarpeta.set(patron)
            resolved = self._resolver_patron_subcarpeta(f"C:/ruta/de/ejemplo/{video_name}.mp4", info, "ESP_subENG", audio_indices, sub_indices)
            self.var_nombre_subcarpeta.set(old_val)
            
            base_dir = self.salida_var.get() or "C:/Salida/Seleccionada"
            preview_lbl.config(text=f"{base_dir}/{resolved}")

        patron_var.trace_add("write", actualizar_preview)
        actualizar_preview()

        def aceptar():
            self.var_nombre_subcarpeta.set(patron_var.get())
            dialog.destroy()

        tk.Button(btm, text="Guardar", command=aceptar, bg="#27AE60", fg="white", width=12, relief=tk.FLAT, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=6)
        tk.Button(btm, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=12, relief=tk.FLAT, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=6)

    def cancelar(self):
        if not self.procesando:
            messagebox.showinfo("Sin proceso", "No hay procesamiento activo")
            return
        if messagebox.askyesno("Cancelar todo", "Deseas cancelar el procesamiento actual y detener toda la cola de videos?"):
            self.cancelar_procesamiento = True
            if self.proceso_actual:
                try:
                    self.proceso_actual.terminate()
                except Exception:
                    pass
            self.btn_cancelar.config(state=tk.DISABLED)
            self.btn_cancelar_asrt.config(state=tk.DISABLED)
            self.btn_cancelar_hst.config(state=tk.DISABLED)
            self._enviar_mensaje("Solicitud de cancelacion enviada...")

    def _run_subprocess_cancellable(self, cmd, stdout_devnull=False):
        self.proceso_actual = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        import time
        while True:
            if self.cancelar_procesamiento:
                try:
                    self.proceso_actual.terminate()
                    self.proceso_actual.wait(timeout=1.5)
                except Exception:
                    try:
                        self.proceso_actual.kill()
                    except Exception:
                        pass
                return subprocess.CompletedProcess(cmd, returncode=-1)
                
            ret = self.proceso_actual.poll()
            if ret is not None:
                return subprocess.CompletedProcess(cmd, returncode=ret)
                
            time.sleep(0.1)

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
        self._iniciar_deteccion_gpus()

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
        gpu_acel = self.gpu_acel_var.get()
        if gpu_acel == "nvidia":
            presets = PRESETS_NVIDIA
            gpu_name = "NVIDIA NVENC"
            orden_presets = ["lossless", "hq", "slow", "bd", "default", "medium", "llhq", "fast", "ll", "llhp", "hp"]
        elif gpu_acel == "intel":
            presets = PRESETS_QSV
            gpu_name = "Intel QSV"
            orden_presets = ["veryslow", "slow", "medium", "fast", "faster", "veryfast"]
        else:
            presets = PRESETS_AMD
            gpu_name = "AMD AMF"
            orden_presets = ["quality", "balanced", "speed"]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Preset - {gpu_name}")
        dialog.geometry("620x420")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text=f"Selecciona preset para {gpu_name}", font=("Segoe UI", 12, "bold")).pack(pady=10)

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
        current = current if current in presets else obtener_preset_valido(current, gpu_acel)
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
        import webbrowser
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Acerca de VPT Studio")
        dialog.geometry("540x370")
        dialog.resizable(False, False)
        dialog.configure(bg="#FFFFFF")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog relative to main window
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        # Top banner frame
        top_banner = tk.Frame(dialog, bg="#1F2A44", height=60)
        top_banner.pack(fill=tk.X)
        top_banner.pack_propagate(False)

        tk.Label(
            top_banner,
            text="VPT Studio",
            font=("Segoe UI", 16, "bold"),
            bg="#1F2A44",
            fg="#FFFFFF"
        ).pack(side=tk.LEFT, padx=20, pady=12)

        tk.Label(
            top_banner,
            text="v2.1.0",
            font=("Segoe UI", 10, "bold"),
            bg="#1F2A44",
            fg="#2D9CDB"
        ).pack(side=tk.RIGHT, padx=20, pady=16)

        # Content frame
        content = tk.Frame(dialog, bg="#FFFFFF", padx=24, pady=16)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            content,
            text="Video Processing Toolkit",
            font=("Segoe UI", 12, "bold"),
            bg="#FFFFFF",
            fg="#1F2A44"
        ).pack(anchor=tk.W)

        desc = (
            "Una suite diseñada para la optimización de flujos de trabajo de vídeo, "
            "automatizando la multiplexación de audio/subtítulos, la codificación acelerada por "
            "hardware (NVIDIA NVENC, Intel QSV, AMD AMF) y la depuración de metadatos."
        )
        tk.Label(
            content,
            text=desc,
            font=("Segoe UI", 9),
            bg="#FFFFFF",
            fg="#5C6B8A",
            justify=tk.LEFT,
            wraplength=490
        ).pack(anchor=tk.W, pady=(6, 10))

        # Divider
        tk.Frame(content, height=1, bg="#E5ECF9").pack(fill=tk.X, pady=(0, 10))

        # Grid for info
        info_frame = tk.Frame(content, bg="#FFFFFF")
        info_frame.pack(fill=tk.X)
        info_frame.columnconfigure(1, weight=1)

        # Developer Row
        tk.Label(
            info_frame,
            text="Desarrollador:",
            font=("Segoe UI", 9, "bold"),
            bg="#FFFFFF",
            fg="#2B3A57"
        ).grid(row=0, column=0, sticky=tk.W, pady=3)

        dev_lbl = tk.Label(
            info_frame,
            text="TheHexenjagd (github.com/TheHexenjagd)",
            font=("Segoe UI", 9, "underline"),
            bg="#FFFFFF",
            fg="#2D9CDB",
            cursor="hand2"
        )
        dev_lbl.grid(row=0, column=1, sticky=tk.W, padx=12, pady=3)
        dev_lbl.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/TheHexenjagd"))

        # Base Projects Row
        tk.Label(
            info_frame,
            text="Proyectos base:",
            font=("Segoe UI", 9, "bold"),
            bg="#FFFFFF",
            fg="#2B3A57"
        ).grid(row=1, column=0, sticky=tk.NW, pady=4)

        projects_subframe = tk.Frame(info_frame, bg="#FFFFFF")
        projects_subframe.grid(row=1, column=1, sticky=tk.W, padx=12, pady=4)

        hardcode_lbl = tk.Label(
            projects_subframe,
            text="• hardcodetool (github.com/TheHexenjagd/hardcodetool)",
            font=("Segoe UI", 9, "underline"),
            bg="#FFFFFF",
            fg="#2D9CDB",
            cursor="hand2"
        )
        hardcode_lbl.pack(anchor=tk.W, pady=1)
        hardcode_lbl.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/TheHexenjagd/hardcodetool"))

        audio_lbl = tk.Label(
            projects_subframe,
            text="• audioselector (github.com/TheHexenjagd/audioselector)",
            font=("Segoe UI", 9, "underline"),
            bg="#FFFFFF",
            fg="#2D9CDB",
            cursor="hand2"
        )
        audio_lbl.pack(anchor=tk.W, pady=1)
        audio_lbl.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/TheHexenjagd/audioselector"))

        # Close button at the bottom
        btn_close = tk.Button(
            dialog,
            text="Cerrar",
            command=dialog.destroy,
            bg="#2D9CDB",
            fg="white",
            activebackground="#2D9CDB",
            activeforeground="white",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_close.pack(side=tk.BOTTOM, pady=12)

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
