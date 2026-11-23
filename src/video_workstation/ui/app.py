import configparser
from datetime import datetime
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk, simpledialog
import tkinter.font as tkfont
import math

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.isdir(_SRC_DIR) and _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from video_workstation import VERSION
from video_workstation.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_CONFIG,
    LOGS_DIR,
    QUEUE_FILE,
    TOOLS_DIR,
)
from video_workstation.constants import (
    BITMAP_SUB_CODECS,
    INCOMPATIBLE_MP4_AUDIO_CODECS,
    PRESETS_AMD,
    PRESETS_NVIDIA,
    PRESETS_QSV,
    STRIP_METADATA_ARGS,
    SUBTITLE_LANGUAGE_MAP as MAPA_IDIOMAS_SRT,
    VIDEO_EXTENSIONS,
)
from video_workstation.media.ffprobe import (
    find_track_by_identifier as encontrar_pista_por_identificador,
    get_track_identifier as obtener_identificador_pista,
    is_hdr_video as _video_es_hdr,
)
from video_workstation.media.paths import resolve_subfolder_pattern as _resolver_patron_subcarpeta_helper
from video_workstation.media.presets import get_valid_preset
from video_workstation.media.presets import get_valid_preset as obtener_preset_valido
from video_workstation.media.subtitles import (
    ensure_external_subtitle_utf8 as asegurar_subtitulo_externo_utf8,
    find_external_subtitles as buscar_subtitulos_externos,
)
from video_workstation.ui.theme import get_theme
from video_workstation.media.processor import MediaProcessorMixin
from video_workstation.ui.dialogs.path_builder import PathBuilderDialogMixin
from video_workstation.ui.dialogs.renamer import RenamerDialogMixin
from video_workstation.ui.dialogs.reports import ReportsDialogMixin
from video_workstation.ui.dialogs.selectors import TrackSelectorDialogMixin
from video_workstation.ui.widgets import (
    ModernCheckbutton,
    RoundedButton,
    attach_treeview_column_dividers,
    center_window,
)
from video_workstation.utils.binaries import (
    get_binary_filename,
    get_default_videos_dir as obtener_directorio_videos_defecto,
    resolve_binary_path as _resolver_ruta_binario,
)
from video_workstation.utils.logger import DailyLogger

tk.Button = RoundedButton


def resolve_app_binary(nombre_binario):
    return _resolver_ruta_binario(nombre_binario, TOOLS_DIR)


class VWSuite(
    MediaProcessorMixin,
    TrackSelectorDialogMixin,
    RenamerDialogMixin,
    PathBuilderDialogMixin,
    ReportsDialogMixin,
):
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Video Workstation (VW)")
        self.root.withdraw()
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

        self.config_ini = self._load_config()
        self.ffmpeg_path = self.config_ini.get("Paths", "ffmpeg", fallback=DEFAULT_CONFIG["Paths"]["ffmpeg"])
        self.ffprobe_path = self.config_ini.get("Paths", "ffprobe", fallback=DEFAULT_CONFIG["Paths"]["ffprobe"])
        if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
            self.ffmpeg_path = resolve_app_binary(get_binary_filename("ffmpeg"))
        if not self.ffprobe_path or not os.path.exists(self.ffprobe_path):
            self.ffprobe_path = resolve_app_binary(get_binary_filename("ffprobe"))

        self.msg_queue = queue.Queue()
        self.procesando = False
        self.cancelar_procesamiento = False
        self.proceso_actual = None
        self.archivo_salida_actual = None
        self.nvenc_verificado = None

        self.pistas_config = {"audio_tag": None, "subtitle_tag": None, "aplicar_a_todos": False}
        self.combinaciones_a_aplicar = {"combinaciones": [], "aplicar_a_todos": False}
        self.subgrupos = {}
        self.combinaciones_por_grupo = {}

        self.ffprobe_cache = {}
        self.theme_var = tk.StringVar(
            value=self.config_ini.get("Options", "tema", fallback="light").lower()
        )
        if self.theme_var.get() not in ("light", "dark"):
            self.theme_var.set("light")

        self._create_styles()
        self._create_menu()
        self._create_ui()
        self._apply_theme()
        self._center_window(1220, 820)
        self.root.deiconify()
        self._check_ffmpeg_on_startup()
        self._start_gpu_detection()

        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)

    def _center_window(self, width=1220, height=820):
        center_window(self.root, width, height)

    def _get_initial_gpu(self):
        val = self.config_ini.get("Options", "gpu_acel", fallback=None)
        if val is None:
            usar_nvidia = self.config_ini.getboolean("Options", "usar_nvidia", fallback=True)
            val = "nvidia" if usar_nvidia else "intel"
        val = val.lower()
        if val not in ("nvidia", "intel", "amd"):
            val = "nvidia"
        return val

    def _load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            try:
                config.read(CONFIG_FILE, encoding="utf-8")
                if config.has_section("Queue"):
                    config.remove_section("Queue")
                    self._save_config(config)
            except Exception:
                for section, values in DEFAULT_CONFIG.items():
                    config[section] = values
                self._save_config(config)
        else:
            for section, values in DEFAULT_CONFIG.items():
                config[section] = values
            self._save_config(config)
        return config

    def _save_config(self, config=None):
        cfg = config if config else self.config_ini
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                cfg.write(f)
        except Exception as exc:
            print(f"Error guardando configuracion: {exc}")

    def _update_config(self, *_):
        try:
            if "Paths" not in self.config_ini:
                self.config_ini["Paths"] = {}
            self.config_ini["Paths"]["ffmpeg"] = self.ffmpeg_path
            self.config_ini["Paths"]["ffprobe"] = self.ffprobe_path
            self.config_ini["Paths"]["output_dir"] = self.salida_var.get()

            if "Options" not in self.config_ini:
                self.config_ini["Options"] = {}
            self.config_ini["Options"]["buscar_recursivo"] = str(self.var_recursivo.get())
            self.config_ini["Options"]["crear_subcarpeta"] = str(self.var_subcarpeta.get())
            self.config_ini["Options"]["nombre_subcarpeta"] = self.var_nombre_subcarpeta.get()
            self.config_ini["Options"]["gpu_acel"] = self.gpu_acel_var.get()
            self.config_ini["Options"]["decod_hw"] = self.decod_hw_var.get()
            self.config_ini["Options"]["usar_nvidia"] = str(self.gpu_acel_var.get() == "nvidia")
            self.config_ini["Options"]["preset"] = self.preset_var.get()
            self.config_ini["Options"]["eliminar_metadatos"] = str(self.var_eliminar_metadatos.get())
            if hasattr(self, "var_buscar_subtitulos_externos"):
                self.config_ini["Options"]["buscar_subtitulos_externos"] = str(self.var_buscar_subtitulos_externos.get())
            if hasattr(self, "theme_var"):
                self.config_ini["Options"]["tema"] = self.theme_var.get()

            self._save_config()
        except Exception as exc:
            print(f"Error actualizando configuracion: {exc}")

    def _on_external_subs_toggle(self, *_):
        self._update_config()
        if hasattr(self, "ffprobe_cache"):
            self.ffprobe_cache.clear()
        self._clear_subgroups()

    def _toggle_theme(self):
        nuevo = "dark" if self.theme_var.get() == "light" else "light"
        self.theme_var.set(nuevo)
        self._update_config()
        self._apply_theme()

    def _create_styles(self):
        t = get_theme(self.theme_var.get() if hasattr(self, "theme_var") else "light")
        self.root.configure(bg=t["bg_app"])
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("VW.TFrame", background=t["bg_app"])
        style.configure("Card.TFrame", background=t["bg_surface"])
        style.configure("CardTitle.TLabel", background=t["bg_surface"], foreground=t["fg_primary"], font=("Segoe UI", 10, "bold"))
        style.configure("Modern.Horizontal.TProgressbar", troughcolor=t["trough"], background=t["accent"], bordercolor=t["trough"], lightcolor=t["accent"], darkcolor=t["accent"])

        style.configure("TNotebook", background=t["bg_surface"], borderwidth=0, tabmargins=(2, 2, 2, 0))
        style.configure("TNotebook.Tab", background=t["bg_tab_inactive"], foreground=t["fg_secondary"], padding=(14, 6), font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map(
            "TNotebook.Tab",
            background=[("selected", t["bg_surface"])],
            foreground=[("selected", t["fg_primary"])],
        )

        style.configure(
            "TCombobox",
            fieldbackground=t["bg_input"],
            background=t["bg_subtle"],
            foreground=t["fg_primary"],
            arrowcolor=t["fg_secondary"],
            bordercolor=t["border"],
            lightcolor=t["bg_input"],
            darkcolor=t["bg_input"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", t["bg_input"])],
            foreground=[("readonly", t["fg_primary"])],
            selectbackground=[("readonly", t["bg_input"])],
            selectforeground=[("readonly", t["fg_primary"])],
        )
        self.root.option_add("*TCombobox*Listbox.background", t["bg_input"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["fg_primary"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", t["accent_fg"])
        try:
            for cb in (getattr(self, "cb_gpu", None), getattr(self, "cb_decod", None), getattr(self, "cb_nombre_subcarpeta", None)):
                if cb is not None and cb.winfo_exists():
                    popdown = cb.tk.eval(f"ttk::combobox::PopdownWindow {cb}")
                    cb.tk.call(f"{popdown}.f.l", "configure", "-background", t["bg_input"], "-foreground", t["fg_primary"], "-selectbackground", t["accent"], "-selectforeground", t["accent_fg"])
        except Exception:
            pass

        style.layout("Activity.Treeview", [("Activity.Treeview.treearea", {"sticky": "nswe"})])
        style.configure(
            "Activity.Treeview",
            font=("Segoe UI", 9),
            rowheight=28,
            background=t["bg_surface"],
            fieldbackground=t["bg_surface"],
            foreground=t["fg_primary"],
            borderwidth=0,
            focusthickness=0,
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=t["heading_bg"],
            foreground=t["heading_fg"],
            relief="flat",
        )
        style.configure(
            "Activity.Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=t["heading_bg"],
            foreground=t["heading_fg"],
            relief="flat",
        )
        style.map(
            "Treeview.Heading",
            background=[("active", t["bg_input"]), ("pressed", t["bg_input"])],
            foreground=[("active", t["fg_primary"]), ("pressed", t["fg_primary"])],
        )
        style.map(
            "Activity.Treeview.Heading",
            background=[("active", t["bg_input"]), ("pressed", t["bg_input"])],
            foreground=[("active", t["fg_primary"]), ("pressed", t["fg_primary"])],
        )
        style.map(
            "Activity.Treeview",
            background=[("selected", t["tree_sel_bg"])],
            foreground=[("selected", t["tree_sel_fg"])],
        )

        style.configure(
            "Vertical.TScrollbar",
            background=t["bg_subtle"],
            troughcolor=t["bg_surface"],
            arrowcolor=t["fg_muted"],
            bordercolor=t["bg_surface"],
            relief="flat",
        )

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        archivo = tk.Menu(menubar, tearoff=0)
        archivo.add_command(label="Salir", command=self.exit_application)
        menubar.add_cascade(label="Archivo", menu=archivo)

        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label="Cambiar ruta de FFmpeg...", command=self.change_ffmpeg_path)
        config_menu.add_command(label="Cambiar ruta de FFProbe...", command=self.change_ffprobe_path)
        config_menu.add_command(label="Preset de codificacion...", command=self.change_preset)
        config_menu.add_separator()
        config_menu.add_command(label="Alternar tema claro / oscuro", command=self._toggle_theme)
        config_menu.add_separator()
        config_menu.add_command(label="Info de rutas FFmpeg/FFProbe", command=self.show_ffmpeg_info)
        menubar.add_cascade(label="Configuracion", menu=config_menu)

        ayuda = tk.Menu(menubar, tearoff=0)
        ayuda.add_command(label="Acerca de...", command=self.show_about)
        menubar.add_cascade(label="Ayuda", menu=ayuda)

        self.root.bind("<F1>", lambda _: self.show_about())

    def _create_ui(self):
        self.var_recursivo = tk.BooleanVar(value=self.config_ini.getboolean("Options", "buscar_recursivo", fallback=True))
        self.var_subcarpeta = tk.BooleanVar(value=self.config_ini.getboolean("Options", "crear_subcarpeta", fallback=False))
        self.var_nombre_subcarpeta = tk.StringVar(value=self.config_ini.get("Options", "nombre_subcarpeta", fallback=""))
        self.gpu_acel_var = tk.StringVar(value=self._get_initial_gpu())
        self.decod_hw_var = tk.StringVar(value=self.config_ini.get("Options", "decod_hw", fallback="Software"))
        self.preset_var = tk.StringVar(value=self.config_ini.get("Options", "preset", fallback="medium"))
        salida_default = self.config_ini.get("Paths", "output_dir", fallback="").strip()
        if not salida_default:
            salida_default = obtener_directorio_videos_defecto()
            if "Paths" not in self.config_ini:
                self.config_ini["Paths"] = {}
            self.config_ini["Paths"]["output_dir"] = salida_default
            self._save_config()
        self.salida_var = tk.StringVar(value=salida_default)
        self.var_eliminar_metadatos = tk.BooleanVar(
            value=self.config_ini.getboolean("Options", "eliminar_metadatos",
                  fallback=self.config_ini.getboolean("Options", "limpiar_metadatos", fallback=False))
        )
        self.var_buscar_subtitulos_externos = tk.BooleanVar(
            value=self.config_ini.getboolean("Options", "buscar_subtitulos_externos", fallback=True)
        )
        self.var_buscar_subtitulos_externos.trace_add("write", self._on_external_subs_toggle)

        for var in [
            self.var_recursivo,
            self.var_subcarpeta,
            self.var_nombre_subcarpeta,
            self.gpu_acel_var,
            self.decod_hw_var,
            self.preset_var,
            self.salida_var,
            self.var_eliminar_metadatos,
        ]:
            var.trace_add("write", self._update_config)

        t = get_theme(self.theme_var.get())
        self._themed_frames = []
        self._themed_labels = []
        self._themed_checks = []
        self._themed_entries = []
        self._themed_dividers = []
        self._themed_buttons = []
        self._current_view = "cola"

        shell = tk.Frame(self.root, bg=t["bg_app"])
        shell.pack(fill=tk.BOTH, expand=True)
        self._themed_frames.append((shell, "bg_app", None))

        # --- BARRA LATERAL (SIDEBAR) ---
        sidebar = tk.Frame(shell, width=230, bg=t["bg_sidebar"], highlightthickness=0, bd=0)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        self._themed_frames.append((sidebar, "bg_sidebar", None))

        side_border = tk.Frame(shell, width=1, bg=t["border"])
        side_border.pack(side=tk.LEFT, fill=tk.Y)
        self._themed_dividers.append(side_border)

        # Marca en sidebar
        brand_box = tk.Frame(sidebar, bg=t["bg_sidebar"])
        brand_box.pack(fill=tk.X, padx=16, pady=(18, 14))
        self._themed_frames.append((brand_box, "bg_sidebar", None))

        brand_row = tk.Frame(brand_box, bg=t["bg_sidebar"])
        brand_row.pack(fill=tk.X)
        self._themed_frames.append((brand_row, "bg_sidebar", None))

        lbl_badge = tk.Label(brand_row, text="VW", font=("Segoe UI", 12, "bold"), bg=t["accent"], fg="#FFFFFF", padx=10, anchor="center")
        lbl_badge.pack(side=tk.LEFT, fill=tk.Y)
        self._lbl_brand_badge = lbl_badge

        brand_txt = tk.Frame(brand_row, bg=t["bg_sidebar"])
        brand_txt.pack(side=tk.LEFT, padx=(10, 0))
        self._themed_frames.append((brand_txt, "bg_sidebar", None))

        lbl_app_name = tk.Label(brand_txt, text="Video Workstation", font=("Segoe UI", 10, "bold"), bg=t["bg_sidebar"], fg=t["fg_primary"])
        lbl_app_name.pack(anchor=tk.W)
        self._themed_labels.append((lbl_app_name, "bg_sidebar", "fg_primary"))

        lbl_app_ver = tk.Label(brand_txt, text=f"v{VERSION}", font=("Segoe UI", 8), bg=t["bg_sidebar"], fg=t["fg_muted"])
        lbl_app_ver.pack(anchor=tk.W)
        self._themed_labels.append((lbl_app_ver, "bg_sidebar", "fg_muted"))

        div_nav_top = tk.Frame(sidebar, height=1, bg=t["border"])
        div_nav_top.pack(fill=tk.X, padx=16, pady=(0, 12))
        self._themed_dividers.append(div_nav_top)

        lbl_nav_sec = tk.Label(sidebar, text="SECCIONES", font=("Segoe UI", 8, "bold"), bg=t["bg_sidebar"], fg=t["fg_muted"])
        lbl_nav_sec.pack(anchor=tk.W, padx=18, pady=(0, 6))
        self._themed_labels.append((lbl_nav_sec, "bg_sidebar", "fg_muted"))

        self._nav_buttons = {}
        nav_defs = [
            ("cola", "Cola principal (0)"),
            ("omitidos", "Omitidos / Errores (0)"),
            ("actividad", "Actividad"),
        ]
        for key, label_txt in nav_defs:
            btn_nav = tk.Button(
                sidebar,
                text=label_txt,
                command=lambda k=key: self._show_view(k),
                bg=t["bg_sidebar"],
                fg=t["fg_secondary"],
                relief=tk.FLAT,
                width=198,
                height=34,
                align="left",
                padx=12,
                font=("Segoe UI", 9, "bold"),
            )
            btn_nav.pack(padx=16, pady=2)
            self._nav_buttons[key] = btn_nav

        div_mant = tk.Frame(sidebar, height=1, bg=t["border"])
        div_mant.pack(fill=tk.X, padx=16, pady=(12, 10))
        self._themed_dividers.append(div_mant)

        lbl_mant_sec = tk.Label(sidebar, text="ACCIONES EN COLA", font=("Segoe UI", 8, "bold"), bg=t["bg_sidebar"], fg=t["fg_muted"])
        lbl_mant_sec.pack(anchor=tk.W, padx=18, pady=(0, 6))
        self._themed_labels.append((lbl_mant_sec, "bg_sidebar", "fg_muted"))

        self.btn_verificar = tk.Button(
            sidebar,
            text="Verificar archivos",
            command=self.verify_queue_files,
            bg=t["bg_sidebar"],
            fg=t["fg_secondary"],
            width=198,
            height=32,
            align="left",
            padx=12,
            font=("Segoe UI", 9),
        )
        self.btn_verificar.pack(padx=16, pady=2)

        self.btn_eliminar_meta = tk.Button(
            sidebar,
            text="Limpiar metadatos",
            command=self.strip_metadata,
            bg=t["bg_sidebar"],
            fg=t["fg_secondary"],
            width=198,
            height=32,
            align="left",
            padx=12,
            font=("Segoe UI", 9),
        )
        self.btn_eliminar_meta.pack(padx=16, pady=2)

        self.btn_eliminar_subs = tk.Button(
            sidebar,
            text="Quitar subtítulos",
            command=self.strip_subtitles,
            bg=t["bg_sidebar"],
            fg=t["fg_secondary"],
            width=198,
            height=32,
            align="left",
            padx=12,
            font=("Segoe UI", 9),
        )
        self.btn_eliminar_subs.pack(padx=16, pady=2)

        self.btn_renombrar = tk.Button(
            sidebar,
            text="Renombrar por lotes",
            command=self.open_renamer,
            bg=t["bg_sidebar"],
            fg=t["fg_secondary"],
            width=198,
            height=32,
            align="left",
            padx=12,
            font=("Segoe UI", 9),
        )
        self.btn_renombrar.pack(padx=16, pady=2)

        self._themed_buttons.extend([
            (self.btn_verificar, "bg_sidebar", "fg_secondary", "bg_sidebar"),
            (self.btn_eliminar_meta, "bg_sidebar", "fg_secondary", "bg_sidebar"),
            (self.btn_eliminar_subs, "bg_sidebar", "fg_secondary", "bg_sidebar"),
            (self.btn_renombrar, "bg_sidebar", "fg_secondary", "bg_sidebar"),
        ])

        # Controles persistentes en parte inferior del sidebar
        side_bottom = tk.Frame(sidebar, bg=t["bg_sidebar"])
        side_bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(8, 16))
        self._themed_frames.append((side_bottom, "bg_sidebar", None))

        div_side_btm = tk.Frame(side_bottom, height=1, bg=t["border"])
        div_side_btm.pack(fill=tk.X, pady=(0, 12))
        self._themed_dividers.append(div_side_btm)

        lbl_exec_sec = tk.Label(side_bottom, text="PROCESAMIENTO", font=("Segoe UI", 8, "bold"), bg=t["bg_sidebar"], fg=t["fg_muted"])
        lbl_exec_sec.pack(anchor=tk.W, padx=2, pady=(0, 6))
        self._themed_labels.append((lbl_exec_sec, "bg_sidebar", "fg_muted"))

        self.btn_procesar_cola = tk.Button(
            side_bottom,
            text="Procesar cola",
            command=self.process_queue,
            bg=t["btn_primary"],
            fg="#FFFFFF",
            width=196,
            height=36,
            font=("Segoe UI", 9, "bold"),
        )
        self.btn_procesar_cola.pack(pady=(0, 6))

        self.btn_cancelar = tk.Button(
            side_bottom,
            text="Cancelar proceso",
            command=self.cancel_processing,
            bg=t["btn_danger"],
            fg="#FFFFFF",
            width=196,
            height=32,
            state=tk.DISABLED,
            font=("Segoe UI", 9, "bold"),
        )
        self.btn_cancelar.pack(pady=0)

        self._themed_buttons.extend([
            (self.btn_procesar_cola, "btn_primary", "accent_fg", "bg_sidebar"),
            (self.btn_cancelar, "btn_danger", "accent_fg", "bg_sidebar"),
        ])

        # --- ÁREA PRINCIPAL (DERECHA) ---
        content_shell = tk.Frame(shell, bg=t["bg_app"])
        content_shell.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._themed_frames.append((content_shell, "bg_app", None))

        # Barra superior contextual
        topbar = tk.Frame(content_shell, height=52, bg=t["bg_surface"], highlightthickness=0)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        self._themed_frames.append((topbar, "bg_surface", None))

        top_border = tk.Frame(content_shell, height=1, bg=t["border"])
        top_border.pack(fill=tk.X)
        self._themed_dividers.append(top_border)

        self.lbl_view_title = tk.Label(topbar, text="Cola de Procesamiento", font=("Segoe UI", 12, "bold"), bg=t["bg_surface"], fg=t["fg_primary"])
        self.lbl_view_title.pack(side=tk.LEFT, padx=20)
        self._themed_labels.append((self.lbl_view_title, "bg_surface", "fg_primary"))

        self.btn_theme = tk.Button(
            topbar,
            text="Tema: Oscuro" if self.theme_var.get() == "light" else "Tema: Claro",
            command=self._toggle_theme,
            bg=t["btn_secondary_bg"],
            fg=t["btn_secondary_fg"],
            width=112,
            height=28,
            font=("Segoe UI", 8, "bold"),
        )
        self.btn_theme.pack(side=tk.RIGHT, padx=(0, 18))
        self._themed_buttons.append((self.btn_theme, "btn_secondary_bg", "btn_secondary_fg", "bg_surface"))

        self.lbl_queue_badge = tk.Label(topbar, text="Cola: 0  |  Omitidos: 0", font=("Segoe UI", 9), bg=t["bg_surface"], fg=t["fg_muted"])
        self.lbl_queue_badge.pack(side=tk.RIGHT, padx=(0, 14))
        self._themed_labels.append((self.lbl_queue_badge, "bg_surface", "fg_muted"))

        self.lbl_top_status = tk.Label(topbar, text="Listo", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["accent"])
        self.lbl_top_status.pack(side=tk.RIGHT, padx=(0, 14))
        self._themed_labels.append((self.lbl_top_status, "bg_surface", "accent"))

        # Contenedor de vistas
        views_container = tk.Frame(content_shell, bg=t["bg_app"])
        views_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)
        self._themed_frames.append((views_container, "bg_app", None))

        # === VISTA 1: COLA PRINCIPAL ===
        view_cola = tk.Frame(views_container, bg=t["bg_app"])
        self._themed_frames.append((view_cola, "bg_app", None))

        queue_card = tk.Frame(view_cola, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        queue_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        self._themed_frames.append((queue_card, "bg_surface", "border"))

        q_header = tk.Frame(queue_card, bg=t["bg_surface"])
        q_header.pack(fill=tk.X, padx=16, pady=(14, 8))
        self._themed_frames.append((q_header, "bg_surface", None))
        lbl_q_hdr = tk.Label(q_header, text="Archivos en cola", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"])
        lbl_q_hdr.pack(side=tk.LEFT)
        self._themed_labels.append((lbl_q_hdr, "bg_surface", "fg_primary"))

        lbl_q_sub = tk.Label(q_header, text="Agrega vídeos o carpetas para procesar por lotes.", font=("Segoe UI", 8), bg=t["bg_surface"], fg=t["fg_muted"])
        lbl_q_sub.pack(side=tk.RIGHT)
        self._themed_labels.append((lbl_q_sub, "bg_surface", "fg_muted"))

        self.lista = tk.Listbox(
            queue_card,
            selectmode=tk.EXTENDED,
            bg=t["bg_subtle"],
            fg=t["fg_primary"],
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
            highlightthickness=1,
            highlightbackground=t["border"],
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self.lista.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 10))

        acciones = tk.Frame(queue_card, bg=t["bg_surface"])
        acciones.pack(fill=tk.X, padx=16, pady=(0, 14))
        self._themed_frames.append((acciones, "bg_surface", None))

        b_add = self._btn(acciones, "Agregar archivos", self.select_files, t["btn_primary"])
        b_add.pack(side=tk.LEFT, padx=(0, 6))
        b_dir = self._btn(acciones, "Cargar carpeta", self.load_folder, t["btn_primary"])
        b_dir.pack(side=tk.LEFT, padx=(0, 6))
        b_rem = self._btn(acciones, "Quitar selección", self.remove_selected_files, t["btn_warning"])
        b_rem.pack(side=tk.LEFT, padx=(0, 6))
        b_clr = self._btn(acciones, "Vaciar cola", self.clear_queue, t["btn_danger"])
        b_clr.pack(side=tk.LEFT, padx=(0, 12))
        self._themed_buttons.extend([
            (b_add, "btn_primary", "accent_fg", "bg_surface"),
            (b_dir, "btn_primary", "accent_fg", "bg_surface"),
            (b_rem, "btn_warning", "accent_fg", "bg_surface"),
            (b_clr, "btn_danger", "accent_fg", "bg_surface"),
        ])

        chk_rec = ModernCheckbutton(
            acciones,
            text="Buscar recursivo",
            variable=self.var_recursivo,
            bg=t["bg_surface"],
            fg=t["fg_secondary"],
            activeforeground=t["fg_primary"],
            selectcolor=t["bg_input"],
            accent=t["accent"],
            border=t["border_strong"],
        )
        chk_rec.pack(side=tk.LEFT, padx=4)
        self._themed_checks.append((chk_rec, "bg_surface", "fg_secondary"))

        # Tarjeta inferior de Salida y Codificación (2 columnas limpias)
        opts_card = tk.Frame(view_cola, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        opts_card.pack(fill=tk.X)
        self._themed_frames.append((opts_card, "bg_surface", "border"))

        opts_grid = tk.Frame(opts_card, bg=t["bg_surface"])
        opts_grid.pack(fill=tk.X, padx=16, pady=12)
        self._themed_frames.append((opts_grid, "bg_surface", None))

        col_dest = tk.Frame(opts_grid, bg=t["bg_surface"])
        col_dest.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 14))
        self._themed_frames.append((col_dest, "bg_surface", None))

        lbl_dest_hdr = tk.Label(col_dest, text="Destino y Organización", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"])
        lbl_dest_hdr.pack(anchor=tk.W, pady=(0, 8))
        self._themed_labels.append((lbl_dest_hdr, "bg_surface", "fg_primary"))

        r_out = tk.Frame(col_dest, bg=t["bg_surface"])
        r_out.pack(fill=tk.X, pady=(0, 6))
        self._themed_frames.append((r_out, "bg_surface", None))
        lbl_out = tk.Label(r_out, text="Salida:", width=10, anchor=tk.W, bg=t["bg_surface"], fg=t["fg_secondary"], font=("Segoe UI", 9))
        lbl_out.pack(side=tk.LEFT)
        self._themed_labels.append((lbl_out, "bg_surface", "fg_secondary"))

        ent_salida = tk.Entry(r_out, textvariable=self.salida_var, bg=t["bg_input"], fg=t["fg_primary"], insertbackground=t["fg_primary"], highlightthickness=1, highlightbackground=t["border"], relief=tk.FLAT)
        ent_salida.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=3)
        self._themed_entries.append(ent_salida)

        b_sel = self._btn(r_out, "Seleccionar", self.select_output_directory, t["btn_info"])
        b_sel.config(width=12)
        b_sel.pack(side=tk.LEFT)
        self._themed_buttons.append((b_sel, "btn_info", "accent_fg", "bg_surface"))

        r_sub = tk.Frame(col_dest, bg=t["bg_surface"])
        r_sub.pack(fill=tk.X)
        self._themed_frames.append((r_sub, "bg_surface", None))
        chk_sub = ModernCheckbutton(r_sub, text="Subcarpeta:", variable=self.var_subcarpeta, bg=t["bg_surface"], fg=t["fg_secondary"], activeforeground=t["fg_primary"], selectcolor=t["bg_input"], accent=t["accent"], border=t["border_strong"])
        chk_sub.pack(side=tk.LEFT, padx=(0, 6))
        self._themed_checks.append((chk_sub, "bg_surface", "fg_secondary"))

        try:
            presets_data = json.loads(self.config_ini.get("Options", "presets", fallback='[]'))
        except Exception:
            presets_data = []
        self.cb_nombre_subcarpeta = ttk.Combobox(r_sub, textvariable=self.var_nombre_subcarpeta, values=presets_data, width=24)
        self.cb_nombre_subcarpeta.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        btn_build = self._btn(r_sub, "Configurar", self._open_path_builder, t["btn_primary"])
        btn_build.config(width=12)
        btn_build.pack(side=tk.LEFT)
        self._themed_buttons.append((btn_build, "btn_primary", "accent_fg", "bg_surface"))

        div_cols = tk.Frame(opts_grid, width=1, bg=t["border"])
        div_cols.pack(side=tk.LEFT, fill=tk.Y, padx=6)
        self._themed_dividers.append(div_cols)

        col_enc = tk.Frame(opts_grid, bg=t["bg_surface"])
        col_enc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 0))
        self._themed_frames.append((col_enc, "bg_surface", None))

        lbl_enc_hdr = tk.Label(col_enc, text="Codificación y Reglas", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"])
        lbl_enc_hdr.pack(anchor=tk.W, pady=(0, 8))
        self._themed_labels.append((lbl_enc_hdr, "bg_surface", "fg_primary"))

        r_hw = tk.Frame(col_enc, bg=t["bg_surface"])
        r_hw.pack(fill=tk.X, pady=(0, 8))
        self._themed_frames.append((r_hw, "bg_surface", None))
        lbl_gpu = tk.Label(r_hw, text="GPU:", bg=t["bg_surface"], fg=t["fg_secondary"], font=("Segoe UI", 9))
        lbl_gpu.pack(side=tk.LEFT, padx=(0, 6))
        self._themed_labels.append((lbl_gpu, "bg_surface", "fg_secondary"))
        self.cb_gpu = ttk.Combobox(r_hw, values=["Detectando..."], state="readonly", width=18)
        self.cb_gpu.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self.cb_gpu.bind("<<ComboboxSelected>>", self._on_gpu_selected)

        lbl_dec = tk.Label(r_hw, text="Decodificador:", bg=t["bg_surface"], fg=t["fg_secondary"], font=("Segoe UI", 9))
        lbl_dec.pack(side=tk.LEFT, padx=(0, 6))
        self._themed_labels.append((lbl_dec, "bg_surface", "fg_secondary"))
        self.cb_decod = ttk.Combobox(r_hw, values=["Software", "D3D11VA", "DXVA2"], state="readonly", textvariable=self.decod_hw_var, width=10)
        self.cb_decod.pack(side=tk.LEFT, padx=(0, 8))
        self.cb_decod.update_idletasks()
        row_h = max(23, self.cb_decod.winfo_reqheight())

        self.btn_preset = tk.Button(
            r_hw,
            text="Preset...",
            command=self.change_preset,
            bg=t["btn_secondary_bg"],
            fg=t["btn_secondary_fg"],
            activebackground=t["btn_secondary_bg"],
            activeforeground=t["btn_secondary_fg"],
            width=14,
            height=row_h,
            pady=0,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )
        self.btn_preset.pack(side=tk.LEFT)
        self._themed_buttons.append((self.btn_preset, "btn_secondary_bg", "btn_secondary_fg", "bg_surface"))
        self.preset_var.trace_add("write", lambda *_: self._update_preset_button_label())
        self.gpu_acel_var.trace_add("write", lambda *_: self._update_preset_button_label())
        self._update_preset_button_label()

        r_chk = tk.Frame(col_enc, bg=t["bg_surface"])
        r_chk.pack(fill=tk.X, pady=(2, 0))
        self._themed_frames.append((r_chk, "bg_surface", None))
        chk_meta = ModernCheckbutton(r_chk, text="Limpiar metadatos al finalizar", variable=self.var_eliminar_metadatos, bg=t["bg_surface"], fg=t["fg_secondary"], activeforeground=t["fg_primary"], selectcolor=t["bg_input"], accent=t["accent"], border=t["border_strong"])
        chk_meta.pack(side=tk.LEFT, padx=(0, 14))
        self._themed_checks.append((chk_meta, "bg_surface", "fg_secondary"))

        chk_ext = ModernCheckbutton(r_chk, text="Incluir subs externos (.srt)", variable=self.var_buscar_subtitulos_externos, bg=t["bg_surface"], fg=t["fg_secondary"], activeforeground=t["fg_primary"], selectcolor=t["bg_input"], accent=t["accent"], border=t["border_strong"])
        chk_ext.pack(side=tk.LEFT)
        self._themed_checks.append((chk_ext, "bg_surface", "fg_secondary"))

        # === VISTA 2: OMITIDOS / ERRORES ===
        view_omitidos = tk.Frame(views_container, bg=t["bg_app"])
        self._themed_frames.append((view_omitidos, "bg_app", None))

        skip_card = tk.Frame(view_omitidos, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        skip_card.pack(fill=tk.BOTH, expand=True)
        self._themed_frames.append((skip_card, "bg_surface", "border"))

        skip_hdr = tk.Frame(skip_card, bg=t["bg_surface"])
        skip_hdr.pack(fill=tk.X, padx=16, pady=(14, 8))
        self._themed_frames.append((skip_hdr, "bg_surface", None))
        lbl_sh = tk.Label(skip_hdr, text="Archivos Omitidos o con Errores", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"])
        lbl_sh.pack(side=tk.LEFT)
        self._themed_labels.append((lbl_sh, "bg_surface", "fg_primary"))

        lbl_sd = tk.Label(skip_hdr, text="Puedes reincorporarlos a la cola principal tras corregir el origen.", font=("Segoe UI", 8), bg=t["bg_surface"], fg=t["fg_muted"])
        lbl_sd.pack(side=tk.RIGHT)
        self._themed_labels.append((lbl_sd, "bg_surface", "fg_muted"))

        self.lista_omitidos = tk.Listbox(
            skip_card,
            selectmode=tk.EXTENDED,
            bg=t["skipped_bg"],
            fg=t["skipped_fg"],
            selectbackground=t["btn_danger"],
            selectforeground="#FFFFFF",
            highlightthickness=1,
            highlightbackground=t["border"],
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self.lista_omitidos.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 10))

        acciones_omitidos = tk.Frame(skip_card, bg=t["bg_surface"])
        acciones_omitidos.pack(fill=tk.X, padx=16, pady=(0, 14))
        self._themed_frames.append((acciones_omitidos, "bg_surface", None))

        b_reinc = self._btn(acciones_omitidos, "Reincorporar", self.requeue_skipped, t["btn_success"])
        b_reinc.pack(side=tk.LEFT, padx=(0, 6))
        b_orem = self._btn(acciones_omitidos, "Quitar selección", self.remove_selected_skipped, t["btn_warning"])
        b_orem.pack(side=tk.LEFT, padx=(0, 6))
        b_oclr = self._btn(acciones_omitidos, "Vaciar lista", self.clear_skipped, t["btn_danger"])
        b_oclr.pack(side=tk.LEFT)
        self._themed_buttons.extend([
            (b_reinc, "btn_success", "accent_fg", "bg_surface"),
            (b_orem, "btn_warning", "accent_fg", "bg_surface"),
            (b_oclr, "btn_danger", "accent_fg", "bg_surface"),
        ])

        # === VISTA 3: ACTIVIDAD ===
        view_act = tk.Frame(views_container, bg=t["bg_app"])
        self._themed_frames.append((view_act, "bg_app", None))

        self._log_lock = threading.Lock()
        self.daily_logger = DailyLogger(LOGS_DIR)
        self._activity_items = {}
        self._act_ok = 0
        self._act_err = 0

        activity_card = tk.Frame(view_act, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        activity_card.pack(fill=tk.BOTH, expand=True)
        self._themed_frames.append((activity_card, "bg_surface", "border"))

        prog = tk.Frame(activity_card, bg=t["bg_surface"])
        prog.pack(fill=tk.X, padx=16, pady=(14, 6))
        self._themed_frames.append((prog, "bg_surface", None))
        self.progress_label = tk.Label(prog, text="Listo", bg=t["bg_surface"], fg=t["fg_muted"], font=("Segoe UI", 9))
        self.progress_label.pack(anchor=tk.W)
        self._themed_labels.append((self.progress_label, "bg_surface", "fg_muted"))
        self.progress = ttk.Progressbar(prog, style="Modern.Horizontal.TProgressbar", mode="determinate")
        self.progress.pack(fill=tk.X, pady=(6, 0))

        act_header = tk.Frame(activity_card, bg=t["bg_surface"])
        act_header.pack(fill=tk.X, padx=16, pady=(8, 0))
        self._themed_frames.append((act_header, "bg_surface", None))
        lbl_act = tk.Label(act_header, text="Registro de Actividad", bg=t["bg_surface"], fg=t["fg_primary"], font=("Segoe UI", 10, "bold"))
        lbl_act.pack(side=tk.LEFT)
        self._themed_labels.append((lbl_act, "bg_surface", "fg_primary"))

        self.btn_ver_log = tk.Button(
            act_header,
            text="Ver log detallado",
            command=self._open_daily_log,
            bg=t["btn_secondary_bg"],
            fg=t["btn_secondary_fg"],
            relief=tk.FLAT,
            padx=12,
            pady=3,
            cursor="hand2",
            font=("Segoe UI", 8, "bold"),
        )
        self.btn_ver_log.pack(side=tk.RIGHT)
        self._themed_buttons.append((self.btn_ver_log, "btn_secondary_bg", "btn_secondary_fg", "bg_surface"))

        self.activity_summary_label = tk.Label(
            act_header,
            text="Éxitos: 0  |  Errores: 0",
            bg=t["bg_surface"],
            fg=t["fg_muted"],
            font=("Segoe UI", 9),
        )
        self.activity_summary_label.pack(side=tk.RIGHT, padx=(0, 14))
        self._themed_labels.append((self.activity_summary_label, "bg_surface", "fg_muted"))

        log_frame = tk.Frame(activity_card, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"], highlightcolor=t["border"])
        log_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(8, 16))
        self._themed_frames.append((log_frame, "bg_surface", "border"))

        cols = ("estado", "video", "accion", "detalle")
        self.activity_tree = ttk.Treeview(log_frame, columns=cols, show="headings", style="Activity.Treeview", height=16, takefocus=False)
        self.activity_tree.bind("<FocusIn>", lambda e: self.root.focus_set())
        self.activity_tree.heading("estado", text="Estado", anchor=tk.W)
        self.activity_tree.heading("video", text="Video", anchor=tk.W)
        self.activity_tree.heading("accion", text="Proceso", anchor=tk.W)
        self.activity_tree.heading("detalle", text="Detalle", anchor=tk.W)

        self.activity_tree.column("estado", width=90, minwidth=80, anchor=tk.W, stretch=False)
        self.activity_tree.column("video", width=480, minwidth=300, anchor=tk.W, stretch=True)
        self.activity_tree.column("accion", width=140, minwidth=115, anchor=tk.W, stretch=False)
        self.activity_tree.column("detalle", width=250, minwidth=180, anchor=tk.W, stretch=True)

        self._activity_tree_update_dividers = attach_treeview_column_dividers(
            self.activity_tree,
            lambda: get_theme(self.theme_var.get())["border_strong"],
        )

        self._tree_tooltip = None

        def _ocultar_tooltip(event=None):
            if self._tree_tooltip:
                try:
                    self._tree_tooltip.destroy()
                except Exception:
                    pass
                self._tree_tooltip = None

        def _mostrar_tooltip(event):
            row_id = self.activity_tree.identify_row(event.y)
            col_id = self.activity_tree.identify_column(event.x)
            if not row_id or not col_id:
                _ocultar_tooltip()
                return

            try:
                col_index = int(col_id.replace("#", "")) - 1
            except ValueError:
                _ocultar_tooltip()
                return

            vals = self.activity_tree.item(row_id, "values")
            if not vals or col_index >= len(vals):
                _ocultar_tooltip()
                return

            texto = str(vals[col_index])
            if len(texto) < 25 and col_index != 1:
                _ocultar_tooltip()
                return

            if self._tree_tooltip and getattr(self._tree_tooltip, "_current_text", None) == texto:
                return

            _ocultar_tooltip()
            tip = tk.Toplevel(self.root)
            tip.wm_overrideredirect(True)
            tip._current_text = texto
            tip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 16}")
            t_curr = get_theme(self.theme_var.get())
            tk.Label(
                tip,
                text=texto,
                bg=t_curr["bg_surface"],
                fg=t_curr["fg_primary"],
                relief=tk.SOLID,
                bd=1,
                padx=8,
                pady=4,
                font=("Segoe UI", 9),
            ).pack()
            self._tree_tooltip = tip

        self.activity_tree.bind("<Motion>", _mostrar_tooltip, add="+")
        self.activity_tree.bind("<Leave>", _ocultar_tooltip, add="+")

        def _limpiar_seleccion_actividad(event):
            if event.widget is self.activity_tree:
                if not self.activity_tree.identify_row(event.y):
                    self.activity_tree.selection_remove(self.activity_tree.selection())
            else:
                if self.activity_tree.selection():
                    self.activity_tree.selection_remove(self.activity_tree.selection())

        self.root.bind("<Button-1>", _limpiar_seleccion_actividad, add="+")

        def _al_mapear_toplevel(event):
            w = event.widget
            if isinstance(w, tk.Toplevel) and not getattr(w, "_vw_themed", False):
                w._vw_themed = True
                self._apply_dialog_theme(w)

        self.root.bind_class("Toplevel", "<Map>", _al_mapear_toplevel, add="+")

        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scr = ttk.Scrollbar(log_frame, orient="vertical", command=self.activity_tree.yview, style="Vertical.TScrollbar")
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.activity_tree.configure(yscrollcommand=scr.set)

        self._views = {
            "cola": view_cola,
            "omitidos": view_omitidos,
            "actividad": view_act,
        }
        self._view_titles = {
            "cola": "Cola de Procesamiento",
            "omitidos": "Omitidos / Errores",
            "actividad": "Actividad y Registro",
        }
        self._show_view("cola")

        try:
            if os.path.exists(QUEUE_FILE):
                queue_ini = configparser.ConfigParser()
                queue_ini.read(QUEUE_FILE, encoding="utf-8")
                if queue_ini.has_section("Queue"):
                    lista_data = json.loads(queue_ini.get("Queue", "lista", fallback="[]"))
                    for f in lista_data:
                        if os.path.exists(f):
                            self.lista.insert(tk.END, os.path.normpath(f))

                    omitidos_data = json.loads(queue_ini.get("Queue", "lista_omitidos", fallback="[]"))
                    for f in omitidos_data:
                        if os.path.exists(f):
                            self.lista_omitidos.insert(tk.END, os.path.normpath(f))
        except Exception as e:
            print(f"Error al cargar cola persistida: {e}")

        self._update_queue_counters()

    def _show_view(self, vista_key):
        self._current_view = vista_key
        for key, frame in self._views.items():
            if key == vista_key:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()
        if hasattr(self, "lbl_view_title"):
            self.lbl_view_title.config(text=self._view_titles.get(vista_key, ""))
        self._update_nav_styles()

    def _update_nav_styles(self):
        t = get_theme(self.theme_var.get())
        if not hasattr(self, "_nav_buttons"):
            return
        for key, btn in self._nav_buttons.items():
            activo = key == self._current_view
            btn.config(
                bg=t["accent"] if activo else t["bg_sidebar"],
                fg="#FFFFFF" if activo else t["fg_secondary"],
                parent_bg=t["bg_sidebar"],
            )

    def _apply_theme(self):
        t = get_theme(self.theme_var.get())
        self._create_styles()

        if hasattr(self, "_lbl_brand_badge"):
            self._lbl_brand_badge.config(bg=t["accent"], fg="#FFFFFF")

        for frame, bg_key, border_key in self._themed_frames:
            kw = {"bg": t[bg_key]}
            if border_key:
                kw["highlightbackground"] = t[border_key]
                kw["highlightcolor"] = t[border_key]
            frame.config(**kw)

        for div in self._themed_dividers:
            div.config(bg=t["border"])

        for lbl, bg_key, fg_key in self._themed_labels:
            lbl.config(bg=t[bg_key], fg=t[fg_key])

        for chk, bg_key, fg_key in self._themed_checks:
            chk.config(
                bg=t[bg_key],
                fg=t[fg_key],
                activebackground=t[bg_key],
                activeforeground=t["fg_primary"],
                selectcolor=t["bg_input"],
                accent=t["accent"],
                border=t["border_strong"],
            )

        for ent in self._themed_entries:
            ent.config(
                bg=t["bg_input"],
                fg=t["fg_primary"],
                insertbackground=t["fg_primary"],
                highlightbackground=t["border"],
                highlightcolor=t["accent"],
            )

        self.lista.config(
            bg=t["bg_subtle"],
            fg=t["fg_primary"],
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
            highlightbackground=t["border"],
        )
        self.lista_omitidos.config(
            bg=t["skipped_bg"],
            fg=t["skipped_fg"],
            selectbackground=t["btn_danger"],
            selectforeground="#FFFFFF",
            highlightbackground=t["border"],
        )

        for btn, bg_key, fg_key, parent_bg_key in self._themed_buttons:
            btn.config(
                bg=t[bg_key],
                fg=t[fg_key],
                disabled_bg=t["btn_disabled_bg"],
                disabled_fg=t["btn_disabled_fg"],
                parent_bg=t[parent_bg_key],
            )

        if hasattr(self, "btn_theme"):
            self.btn_theme.config(
                text="Tema: Oscuro" if self.theme_var.get() == "light" else "Tema: Claro"
            )

        self.activity_tree.tag_configure("exito", foreground=t["success"], background=t["success_bg"])
        self.activity_tree.tag_configure("error", foreground=t["danger"], background=t["danger_bg"])
        self.activity_tree.tag_configure("procesando", foreground=t["info"], background=t["info_bg"])
        self.activity_tree.tag_configure("aviso", foreground=t["warning"], background=t["warning_bg"])
        self._update_nav_styles()

    def _apply_dialog_theme(self, win):
        """Aplica la paleta activa (clara u oscura) de forma recursiva a cualquier ventana secundaria."""
        if not win or not win.winfo_exists():
            return
        t = get_theme(self.theme_var.get())
        win.configure(bg=t["bg_app"])

        bg_superficie = {"#FFFFFF", "#F9FBFF"}
        bg_sutil = {"#E5ECF9", "#EEF3FB", "#F4F8FF"}
        bg_app = {"#F3F7FF", "SYSTEMBUTTONFACE", "WHITE"}
        fg_oscuro_a_primario = {"#1F2A44", "#2B3A57", "#4F4F4F", "#000000", "BLACK", "SYSTEMWINDOWTEXT"}
        fg_tenue_a_muted = {"#5C6B8A", "#7F8C8D", "#B0C4DE", "#95A5A6"}
        fg_acento = {"#2D9CDB", "#2F80ED", "#4DA8DA"}

        def _recorrer(widget, parent_bg):
            for child in widget.winfo_children():
                try:
                    if isinstance(child, RoundedButton):
                        child.config(
                            parent_bg=parent_bg,
                            disabled_bg=t["btn_disabled_bg"],
                            disabled_fg=t["btn_disabled_fg"],
                        )
                        continue

                    if isinstance(child, (tk.Frame, tk.LabelFrame)):
                        cur_bg = str(child.cget("bg")).upper()
                        if cur_bg in ("#1A2536", "#1C2541"):
                            new_bg = t["bg_sidebar"]
                        elif cur_bg in ("#2D9CDB", "#2563EB"):
                            new_bg = t["accent"]
                        elif cur_bg in ("#E5ECF9", "#D1E2FF") and str(child.cget("height")) == "1":
                            new_bg = t["border"]
                        elif cur_bg in bg_superficie:
                            new_bg = t["bg_surface"]
                        elif cur_bg in bg_sutil:
                            new_bg = t["bg_subtle"]
                        elif cur_bg in bg_app:
                            new_bg = t["bg_app"]
                        else:
                            new_bg = parent_bg

                        kw = {"bg": new_bg}
                        if isinstance(child, tk.LabelFrame):
                            kw["fg"] = t["fg_primary"]
                        try:
                            if int(str(child.cget("highlightthickness")) or 0) > 0:
                                kw["highlightbackground"] = t["border"]
                                kw["highlightcolor"] = t["border"]
                        except Exception:
                            pass
                        child.config(**kw)
                        _recorrer(child, new_bg)
                    elif isinstance(child, tk.Label):
                        cur_bg = str(child.cget("bg")).upper()
                        cur_fg = str(child.cget("fg")).upper()
                        if cur_bg in ("#2563EB", "#3B82F6", "#2D9CDB"):
                            child.config(bg=t["accent"], fg="#FFFFFF")
                            continue
                        if cur_fg in fg_oscuro_a_primario:
                            new_fg = t["fg_primary"]
                        elif cur_fg in fg_tenue_a_muted:
                            new_fg = t["fg_muted"]
                        elif cur_fg in fg_acento:
                            new_fg = t["accent"]
                        elif cur_fg in ("#EB5757", "#E74C3C"):
                            new_fg = t["danger"]
                        elif cur_fg in ("#27AE60", "#1E8449"):
                            new_fg = t["success"]
                        elif cur_fg in ("#F2994A", "#F2C94C"):
                            new_fg = t["warning"]
                        else:
                            new_fg = child.cget("fg")
                        child.config(bg=parent_bg, fg=new_fg)
                    elif isinstance(child, (tk.Checkbutton, tk.Radiobutton)):
                        child.config(
                            bg=parent_bg,
                            fg=t["fg_primary"],
                            activebackground=parent_bg,
                            activeforeground=t["fg_primary"],
                            selectcolor=t["bg_input"],
                        )
                    elif isinstance(child, (tk.Entry, tk.Spinbox)):
                        kw_ent = {
                            "bg": t["bg_input"],
                            "fg": t["fg_primary"],
                            "insertbackground": t["fg_primary"],
                        }
                        if isinstance(child, tk.Spinbox):
                            kw_ent["buttonbackground"] = t["bg_subtle"]
                        child.config(**kw_ent)
                    elif isinstance(child, tk.Text):
                        child.config(
                            bg=t["bg_subtle"],
                            fg=t["fg_primary"],
                            insertbackground=t["fg_primary"],
                        )
                    elif isinstance(child, tk.Listbox):
                        child.config(
                            bg=t["bg_subtle"],
                            fg=t["fg_primary"],
                            selectbackground=t["accent"],
                            selectforeground=t["accent_fg"],
                        )
                    elif isinstance(child, tk.Canvas):
                        child.config(bg=parent_bg)
                        _recorrer(child, parent_bg)
                    else:
                        _recorrer(child, parent_bg)
                except Exception:
                    try:
                        _recorrer(child, parent_bg)
                    except Exception:
                        pass

        _recorrer(win, t["bg_app"])

        if hasattr(self, "_activity_tree_update_dividers") and callable(self._activity_tree_update_dividers):
            self._activity_tree_update_dividers()

    def _update_queue_counters(self):
        cant_activos = len([f for f in self.lista.get(0, tk.END) if f and str(f).strip()])
        cant_omitidos = len([f for f in self.lista_omitidos.get(0, tk.END) if f and str(f).strip()])
        if hasattr(self, "_nav_buttons"):
            if "cola" in self._nav_buttons:
                self._nav_buttons["cola"].config(text=f"Cola principal ({cant_activos})")
            if "omitidos" in self._nav_buttons:
                self._nav_buttons["omitidos"].config(text=f"Omitidos / Errores ({cant_omitidos})")
        if hasattr(self, "lbl_queue_badge"):
            self.lbl_queue_badge.config(text=f"Cola: {cant_activos}  |  Omitidos: {cant_omitidos}")
        return cant_activos, cant_omitidos

    def _update_preset_button_label(self):
        """Keep the Preset button label in sync with the active GPU and preset."""
        if not hasattr(self, "btn_preset"):
            return
        gpu = self.gpu_acel_var.get()
        if gpu in ("nvidia", "intel", "amd"):
            valid = get_valid_preset(self.preset_var.get(), gpu)
            self.btn_preset.config(text=f"Preset: {valid.upper()}")
        else:
            self.btn_preset.config(text="Preset: N/D")

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
            width=16,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

    def _get_daily_log_path(self):
        return self.daily_logger.get_daily_path()

    def _write_log_file(self, msg, separador=False):
        self.daily_logger.write(msg, separator=separador)

    def _open_daily_log(self):
        ruta_log = self._get_daily_log_path()
        objetivo = ruta_log if os.path.exists(ruta_log) else LOGS_DIR
        try:
            if sys.platform.startswith("win"):
                os.startfile(objetivo)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", objetivo])
            else:
                subprocess.Popen(["xdg-open", objetivo])
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo abrir el registro:\n{exc}")

    def _log_message(self, msg):
        self._write_log_file(msg)

    def _record_activity(self, estado, video, accion, detalle="", item_key=None, log_extra=None):
        if estado != "procesando":
            lineas = [f"[{estado.upper()}] {accion}  |  {video}"]
            if detalle:
                lineas.append(f"  Detalle: {detalle}")
            if log_extra:
                for k, v in log_extra.items():
                    lineas.append(f"  {k}: {v}")
            self._write_log_file("\n".join(lineas))
        self.msg_queue.put(("ACTIVIDAD", estado, video, accion, detalle, item_key))

    def _update_activity_ui(self, estado, video, accion, detalle, item_key=None):
        etiquetas = {
            "procesando": "Procesando",
            "exito": "Éxito",
            "error": "Error",
            "aviso": "Aviso",
        }
        estado_txt = etiquetas.get(estado, estado)
        tag = estado if estado in etiquetas else "procesando"
        valores = (estado_txt, video, accion, detalle)

        if item_key and item_key in self._activity_items:
            item_id = self._activity_items[item_key]
            prev_tags = self.activity_tree.item(item_id, "tags")
            if "exito" in prev_tags:
                self._act_ok = max(0, self._act_ok - 1)
            elif "error" in prev_tags:
                self._act_err = max(0, self._act_err - 1)
            self.activity_tree.item(item_id, values=valores, tags=(tag,))
        else:
            item_id = self.activity_tree.insert("", tk.END, values=valores, tags=(tag,))
            if item_key:
                self._activity_items[item_key] = item_id

        if estado == "exito":
            self._act_ok += 1
        elif estado == "error":
            self._act_err += 1

        self.activity_summary_label.config(text=f"Éxitos: {self._act_ok}  |  Errores: {self._act_err}")
        self.activity_tree.see(item_id)

    def _poll_ui_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if isinstance(msg, tuple):
                    if msg[0] == "PROGRESO":
                        _, actual, total = msg
                        pct = (actual / total) * 100 if total else 0
                        self.progress["value"] = pct
                        estado_str = f"Procesando {actual}/{total} ({pct:.1f}%)"
                        self.progress_label.config(text=estado_str)
                        if hasattr(self, "lbl_top_status"):
                            self.lbl_top_status.config(text=estado_str)
                    elif msg[0] == "FINALIZADO":
                        ok = msg[1]
                        fail = msg[2]
                        errores = msg[3] if len(msg) > 3 else []
                        fue_cancelado = msg[4] if len(msg) > 4 else False
                        archivos_exitosos = msg[5] if len(msg) > 5 else []

                        self.progress["value"] = 100
                        if fue_cancelado:
                            fin_str = f"Cancelado | Éxitos: {ok} | Fallos: {fail}"
                        else:
                            fin_str = f"Completado | Éxitos: {ok} | Fallos: {fail}"
                        self.progress_label.config(text=fin_str)
                        if hasattr(self, "lbl_top_status"):
                            self.lbl_top_status.config(text="Cancelado" if fue_cancelado else "Completado")
                        self._set_running_state(False)

                        if hasattr(self, "archivos_en_proceso") and self.archivos_en_proceso:

                            norm_proc = {os.path.normcase(os.path.normpath(p)) for p in self.archivos_en_proceso}
                            norm_exito = {os.path.normcase(os.path.normpath(p)) for p in archivos_exitosos}

                            failed_files_norm = set()
                            for err in errores:
                                if err and isinstance(err, tuple) and len(err) > 0:
                                    failed_files_norm.add(os.path.normcase(os.path.normpath(err[0])))

                            all_items = list(self.lista.get(0, tk.END))
                            self.lista.delete(0, tk.END)
                            for f in all_items:
                                f_norm = os.path.normcase(os.path.normpath(f))
                                if f_norm in norm_proc:
                                    if f_norm in failed_files_norm:

                                        existentes_norm = {os.path.normcase(os.path.normpath(x)) for x in self.lista_omitidos.get(0, tk.END)}
                                        if f_norm not in existentes_norm:
                                            self.lista_omitidos.insert(tk.END, f)
                                    elif fue_cancelado:

                                        if f_norm not in norm_exito:
                                            self.lista.insert(tk.END, f)

                                else:

                                    self.lista.insert(tk.END, f)

                            self.archivos_en_proceso = []

                            self._update_queue_counters()

                            if failed_files_norm:
                                self._show_view("omitidos")

                        self._clear_subgroups()

                        title = "Proceso cancelado" if fue_cancelado else "Completado"
                        desc = "El procesamiento fue cancelado por el usuario." if fue_cancelado else "Proceso terminado."
                        messagebox.showinfo(title, f"{desc}\n\nExitos: {ok}\nFallos: {fail}")

                        total = ok + fail
                        if total > 1 and fail > 0 and errores:
                            self._show_error_summary(errores)
                    elif msg[0] == "ACTIVIDAD":
                        _, estado, video, accion, detalle, item_key = msg
                        self._update_activity_ui(estado, video, accion, detalle, item_key)
                    elif msg[0] == "SELECTOR_PISTAS":
                        _, info, filename, q = msg
                        if self.cancelar_procesamiento:
                            q.put({"ok": False, "audio": None, "subtitle": None, "aplicar_todos": False})
                        else:
                            q.put(self._show_track_selector(info, filename))
                    elif msg[0] == "SELECTOR_COMBINACIONES":
                        _, info, filename, subgrupo_label, q = msg
                        if self.cancelar_procesamiento:
                            q.put({"ok": False, "combinaciones": [], "aplicar_todos": False})
                        else:
                            q.put(self._show_combination_selector(info, filename, subgrupo_label))
        except queue.Empty:
            pass

        if self.procesando or not self.msg_queue.empty():
            self.root.after(100, self._poll_ui_queue)

    def _move_to_skipped(self, archivos):
        archivos_set = set(archivos)

        all_items = list(self.lista.get(0, tk.END))
        self.lista.delete(0, tk.END)
        for f in all_items:
            if f not in archivos_set:
                self.lista.insert(tk.END, f)

        existentes = set(self.lista_omitidos.get(0, tk.END))
        for f in archivos:
            if f not in existentes:
                self.lista_omitidos.insert(tk.END, f)

        self._update_queue_counters()
        self._show_view("omitidos")

    def requeue_skipped(self):
        sel = self.lista_omitidos.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona elementos en la lista de omitidos", parent=self.root)
            return

        items_to_move = [self.lista_omitidos.get(i) for i in sel]

        for i in reversed(sel):
            self.lista_omitidos.delete(i)

        existentes = set(self.lista.get(0, tk.END))
        for item in items_to_move:
            if item not in existentes:
                self.lista.insert(tk.END, item)

        self._update_queue_counters()
        self._clear_subgroups()
        self._show_view("cola")

    def remove_selected_skipped(self):
        sel = self.lista_omitidos.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona elementos en la lista de omitidos", parent=self.root)
            return
        for i in reversed(sel):
            self.lista_omitidos.delete(i)
        self._update_queue_counters()

    def clear_skipped(self):
        if self.lista_omitidos.size() == 0:
            return
        if messagebox.askyesno("Confirmar", "Deseas limpiar todos los archivos omitidos?", parent=self.root):
            self.lista_omitidos.delete(0, tk.END)
            self._update_queue_counters()

    def _set_running_state(self, running):
        self.btn_procesar_cola.config(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_verificar.config(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_eliminar_meta.config(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_eliminar_subs.config(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_renombrar.config(state=tk.DISABLED if running else tk.NORMAL)
        cancel_state = tk.NORMAL if running else tk.DISABLED
        self.btn_cancelar.config(state=cancel_state)

    def _clear_log_and_progress(self, status):
        self.activity_tree.delete(*self.activity_tree.get_children())
        self._activity_items = {}
        self._act_ok = 0
        self._act_err = 0
        self.activity_summary_label.config(text="Éxitos: 0  |  Errores: 0")
        self.progress["value"] = 0
        self.progress_label.config(text=status)
        if hasattr(self, "lbl_top_status"):
            self.lbl_top_status.config(text=status)
        self._write_log_file(status, separador=True)
        if hasattr(self, "_views"):
            self._show_view("actividad")

    def select_files(self):
        files = filedialog.askopenfilenames(title="Seleccionar videos", filetypes=[("Videos", "*.mp4 *.mkv *.mov *.avi *.flv *.webm *.ts *.m4v")])
        for f in files:
            self.lista.insert(tk.END, os.path.normpath(f))
        self._update_queue_counters()

    def load_folder(self):
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
        self._update_queue_counters()

        messagebox.showinfo("Carga finalizada", f"Se agregaron {len(encontrados)} archivo(s)")

    def remove_selected_files(self):
        sel = self.lista.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona elementos")
            return
        for i in reversed(sel):
            self.lista.delete(i)
        self._update_queue_counters()
        self._clear_subgroups()

    def clear_queue(self):
        if self.lista.size() == 0:
            return
        if messagebox.askyesno("Confirmar", "Deseas limpiar toda la lista?"):
            self.lista.delete(0, tk.END)
            self._update_queue_counters()
            if hasattr(self, "ffprobe_cache"):
                self.ffprobe_cache.clear()
            self._clear_subgroups()

    def select_output_directory(self):
        dir_inicial = self.salida_var.get().strip() or obtener_directorio_videos_defecto()
        carpeta = filedialog.askdirectory(title="Seleccionar salida", initialdir=dir_inicial)
        if carpeta:
            self.salida_var.set(carpeta)

    def change_ffmpeg_path(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar ffmpeg.exe",
            filetypes=[("FFmpeg", "ffmpeg.exe"), ("Todos", "*.*")],
            initialdir=os.path.dirname(self.ffmpeg_path) if (self.ffmpeg_path and os.path.exists(os.path.dirname(self.ffmpeg_path))) else TOOLS_DIR,
        )
        if not archivo:
            return

        self.ffmpeg_path = archivo
        ffprobe_same = os.path.join(os.path.dirname(archivo), "ffprobe.exe")
        if os.path.exists(ffprobe_same):
            self.ffprobe_path = ffprobe_same
            self._show_themed_notice("Rutas actualizadas", f"FFmpeg y FFProbe actualizados:\n{archivo}")
        else:
            self._show_themed_notice(
                "FFmpeg actualizado",
                f"FFmpeg actualizado:\n{archivo}\n\nSelecciona FFProbe manualmente si hace falta.",
            )
        self._update_config()
        self._start_gpu_detection()

    def change_ffprobe_path(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar ffprobe.exe",
            filetypes=[("FFProbe", "ffprobe.exe"), ("Todos", "*.*")],
            initialdir=os.path.dirname(self.ffprobe_path) if (self.ffprobe_path and os.path.exists(os.path.dirname(self.ffprobe_path))) else TOOLS_DIR,
        )
        if archivo:
            self.ffprobe_path = archivo
            self._update_config()
            self._show_themed_notice("FFProbe actualizado", f"FFProbe actualizado:\n{archivo}")

    def _show_themed_notice(self, title, message, kind="info", parent=None):
        """Show a studio-themed modal notification instead of a native Windows messagebox."""
        t = get_theme(self.theme_var.get())
        owner = parent if (parent is not None and parent.winfo_exists()) else self.root
        badge_bg = t["danger"] if kind == "error" else (t["warning"] if kind == "warning" else t["accent"])
        badge_txt = "!" if kind in ("error", "warning") else "VW"

        dlg = tk.Toplevel(owner)
        dlg.withdraw()
        dlg.title(f"{title} - VW")
        dlg.resizable(False, False)
        dlg.transient(owner)
        dlg.grab_set()
        dlg.configure(bg=t["bg_app"])
        owner.attributes("-disabled", True)
        dlg.bind(
            "<Destroy>",
            lambda e: owner.attributes("-disabled", False)
            if (e.widget == dlg and owner.winfo_exists())
            else None,
        )

        hdr = tk.Frame(dlg, bg=t["bg_surface"], padx=16, pady=12)
        hdr.pack(fill=tk.X)
        tk.Label(
            hdr,
            text=badge_txt,
            font=("Segoe UI", 10, "bold"),
            bg=badge_bg,
            fg=t["accent_fg"],
            padx=8,
            pady=3,
        ).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(
            hdr,
            text=title,
            font=("Segoe UI", 11, "bold"),
            bg=t["bg_surface"],
            fg=t["fg_primary"],
            anchor=tk.W,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Frame(dlg, height=1, bg=t["border"]).pack(fill=tk.X)

        btm = tk.Frame(dlg, bg=t["bg_app"], padx=16, pady=12)
        btm.pack(side=tk.BOTTOM, fill=tk.X)
        btn_ok = tk.Button(
            btm,
            text="Aceptar",
            command=dlg.destroy,
            bg=t["btn_primary"],
            fg=t["accent_fg"],
            width=12,
        )
        btn_ok.pack(side=tk.RIGHT)

        body = tk.Frame(dlg, bg=t["bg_app"], padx=16, pady=12)
        body.pack(fill=tk.BOTH, expand=True)
        card = tk.Frame(
            body,
            bg=t["bg_surface"],
            highlightthickness=1,
            highlightbackground=t["border"],
            padx=14,
            pady=12,
        )
        card.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            card,
            text=message,
            font=("Segoe UI", 9),
            bg=t["bg_surface"],
            fg=t["fg_secondary"],
            justify=tk.LEFT,
            wraplength=390,
            anchor=tk.NW,
        ).pack(fill=tk.BOTH, expand=True)

        dlg.update_idletasks()
        w = max(460, dlg.winfo_reqwidth())
        h = max(230, dlg.winfo_reqheight())
        center_window(dlg, w, h, owner)

        dlg.bind("<Return>", lambda _: dlg.destroy())
        dlg.bind("<Escape>", lambda _: dlg.destroy())
        dlg.wait_window()

    def show_ffmpeg_info(self):
        t = get_theme(self.theme_var.get())
        dlg = tk.Toplevel(self.root)
        dlg.withdraw()
        dlg.title("Rutas configuradas - VW")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=t["bg_app"])
        self.root.attributes("-disabled", True)
        dlg.bind(
            "<Destroy>",
            lambda e: self.root.attributes("-disabled", False)
            if (e.widget == dlg and self.root.winfo_exists())
            else None,
        )

        hdr = tk.Frame(dlg, bg=t["bg_surface"], padx=18, pady=14)
        hdr.pack(fill=tk.X)
        tk.Label(
            hdr,
            text="VW",
            font=("Segoe UI", 10, "bold"),
            bg=t["accent"],
            fg=t["accent_fg"],
            padx=8,
            pady=4,
        ).pack(side=tk.LEFT, padx=(0, 12))
        hdr_txt = tk.Frame(hdr, bg=t["bg_surface"])
        hdr_txt.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(
            hdr_txt,
            text="Rutas configuradas",
            font=("Segoe UI", 12, "bold"),
            bg=t["bg_surface"],
            fg=t["fg_primary"],
            anchor=tk.W,
        ).pack(fill=tk.X)
        tk.Label(
            hdr_txt,
            text="Ubicaciones activas de binarios y configuración",
            font=("Segoe UI", 9),
            bg=t["bg_surface"],
            fg=t["fg_secondary"],
            anchor=tk.W,
        ).pack(fill=tk.X)

        tk.Frame(dlg, height=1, bg=t["border"]).pack(fill=tk.X)

        btm = tk.Frame(dlg, bg=t["bg_app"], padx=18, pady=12)
        btm.pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(dlg, bg=t["bg_app"], padx=18, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(
            body,
            bg=t["bg_surface"],
            highlightthickness=1,
            highlightbackground=t["border"],
            padx=16,
            pady=12,
        )
        card.pack(fill=tk.BOTH, expand=True)

        rows = [
            ("FFmpeg", self.ffmpeg_path, os.path.exists(self.ffmpeg_path) if self.ffmpeg_path else False),
            ("FFProbe", self.ffprobe_path, os.path.exists(self.ffprobe_path) if self.ffprobe_path else False),
            ("Configuración VW", CONFIG_DIR, os.path.isdir(CONFIG_DIR)),
            ("Carpeta Tools", TOOLS_DIR, os.path.isdir(TOOLS_DIR)),
        ]

        for idx, (label, path_val, exists) in enumerate(rows):
            row = tk.Frame(card, bg=t["bg_surface"])
            row.pack(fill=tk.X, pady=(0, 8 if idx < len(rows) - 1 else 0))

            top = tk.Frame(row, bg=t["bg_surface"])
            top.pack(fill=tk.X, pady=(0, 3))
            tk.Label(
                top,
                text=label,
                font=("Segoe UI", 9, "bold"),
                bg=t["bg_surface"],
                fg=t["fg_primary"],
            ).pack(side=tk.LEFT)
            tk.Label(
                top,
                text="Disponible" if exists else "No encontrado",
                font=("Segoe UI", 8, "bold"),
                bg=t["success_bg"] if exists else t["danger_bg"],
                fg=t["success"] if exists else t["danger"],
                padx=7,
                pady=1,
            ).pack(side=tk.RIGHT)

            tk.Label(
                row,
                text=path_val or "(sin definir)",
                font=("Consolas", 8),
                bg=t["bg_input"],
                fg=t["fg_secondary"],
                anchor=tk.W,
                padx=8,
                pady=5,
                wraplength=520,
                justify=tk.LEFT,
            ).pack(fill=tk.X)

        def _copy_paths():
            summary = "\n".join(f"{lbl}: {val}" for lbl, val, _ in rows)
            dlg.clipboard_clear()
            dlg.clipboard_append(summary)
            btn_copy.config(text="Copiado")
            dlg.after(1500, lambda: btn_copy.config(text="Copiar rutas") if dlg.winfo_exists() else None)

        btn_copy = tk.Button(
            btm,
            text="Copiar rutas",
            command=_copy_paths,
            bg=t["btn_secondary_bg"],
            fg=t["btn_secondary_fg"],
            width=14,
        )
        btn_copy.pack(side=tk.LEFT)
        tk.Button(
            btm,
            text="Cerrar",
            command=dlg.destroy,
            bg=t["btn_primary"],
            fg=t["accent_fg"],
            width=12,
        ).pack(side=tk.RIGHT)

        dlg.update_idletasks()
        w = max(600, dlg.winfo_reqwidth())
        h = max(440, dlg.winfo_reqheight())
        center_window(dlg, w, h, self.root)

    def exit_application(self):
        if self.procesando:
            confirmar = messagebox.askyesno(
                "Proceso activo",
                "Hay un proceso en curso.\n¿Deseas cancelarlo y salir de todos modos?",
                parent=self.root,
            )
            if not confirmar:
                return

            self.cancelar_procesamiento = True
            if hasattr(self, "_clear_subgroups") and callable(self._clear_subgroups):
                try:
                    self._clear_subgroups()
                except Exception:
                    pass

            proc = getattr(self, "proceso_actual", None)
            if proc:
                try:
                    if os.name == "nt" and proc.pid:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        )
                except Exception:
                    pass
                try:
                    proc.kill()
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                try:
                    proc.wait(timeout=1.0)
                except Exception:
                    pass

            salida_actual = getattr(self, "archivo_salida_actual", None)
            if salida_actual:
                try:
                    p = Path(salida_actual)
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
                self.archivo_salida_actual = None

            self.procesando = False

        cant_activos, cant_omitidos = self._update_queue_counters()
        if cant_activos > 0 or cant_omitidos > 0:
            guardar = messagebox.askyesno(
                "Guardar cola",
                "¿Deseas guardar la lista actual de videos y omitidos para la próxima sesión?",
                parent=self.root
            )
            if guardar:
                validos_activos = [f for f in self.lista.get(0, tk.END) if f and str(f).strip()]
                validos_omitidos = [f for f in self.lista_omitidos.get(0, tk.END) if f and str(f).strip()]
                queue_ini = configparser.ConfigParser()
                queue_ini.add_section("Queue")
                queue_ini.set("Queue", "lista", json.dumps(validos_activos))
                queue_ini.set("Queue", "lista_omitidos", json.dumps(validos_omitidos))
                try:
                    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                        queue_ini.write(f)
                except Exception as exc:
                    print(f"Error guardando cola: {exc}")
            else:
                if os.path.exists(QUEUE_FILE):
                    try:
                        os.remove(QUEUE_FILE)
                    except Exception as exc:
                        print(f"Error eliminando archivo de cola: {exc}")
        else:
            if os.path.exists(QUEUE_FILE):
                try:
                    os.remove(QUEUE_FILE)
                except Exception as exc:
                    print(f"Error eliminando archivo de cola: {exc}")

        if self.config_ini.has_section("Queue"):
            self.config_ini.remove_section("Queue")

        self._update_config()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

def main():
    app = VWSuite()
    app.run()


if __name__ == "__main__":
    main()
