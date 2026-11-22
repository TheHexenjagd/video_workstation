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
from video_workstation.media.presets import get_valid_preset as obtener_preset_valido
from video_workstation.media.subtitles import (
    ensure_external_subtitle_utf8 as asegurar_subtitulo_externo_utf8,
    find_external_subtitles as buscar_subtitulos_externos,
)
from video_workstation.ui.theme import get_theme
from video_workstation.ui.widgets import RoundedButton
from video_workstation.utils.binaries import (
    get_app_base_dir as obtener_ruta_base_app,
    get_default_videos_dir as obtener_directorio_videos_defecto,
    resolve_binary_path as _resolver_ruta_binario,
)
from video_workstation.utils.logger import DailyLogger

tk.Button = RoundedButton


def resolve_app_binary(nombre_binario):
    return _resolver_ruta_binario(nombre_binario, TOOLS_DIR)


class VWSuite:
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
            self.ffmpeg_path = resolve_app_binary("ffmpeg.exe")
        if not self.ffprobe_path or not os.path.exists(self.ffprobe_path):
            self.ffprobe_path = resolve_app_binary("ffprobe.exe")

        self.msg_queue = queue.Queue()
        self.procesando = False
        self.cancelar_procesamiento = False
        self.proceso_actual = None
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
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        # Compensar barra de título + menú (~56px) y barra de tareas (~48px)
        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - 48 - (height + 56)) // 2)
        self.root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

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
            "Activity.Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=t["heading_bg"],
            foreground=t["heading_fg"],
            bordercolor=t["border"],
            relief="flat",
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

        lbl_badge = tk.Label(brand_row, text="VW", font=("Segoe UI", 12, "bold"), bg=t["accent"], fg="#FFFFFF", padx=8, pady=3)
        lbl_badge.pack(side=tk.LEFT)
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

        lbl_mant_sec = tk.Label(sidebar, text="MANTENIMIENTO", font=("Segoe UI", 8, "bold"), bg=t["bg_sidebar"], fg=t["fg_muted"])
        lbl_mant_sec.pack(anchor=tk.W, padx=18, pady=(0, 6))
        self._themed_labels.append((lbl_mant_sec, "bg_sidebar", "fg_muted"))

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

        lbl_exec_sec = tk.Label(side_bottom, text="EJECUCIÓN", font=("Segoe UI", 8, "bold"), bg=t["bg_sidebar"], fg=t["fg_muted"])
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

        self.btn_verificar = tk.Button(
            side_bottom,
            text="Verificar archivos",
            command=self.verify_queue_files,
            bg=t["btn_secondary_bg"],
            fg=t["btn_secondary_fg"],
            width=196,
            height=32,
            font=("Segoe UI", 9, "bold"),
        )
        self.btn_verificar.pack(pady=(0, 6))

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
        self.btn_cancelar.pack(pady=(0, 6))

        self._themed_buttons.extend([
            (self.btn_procesar_cola, "btn_primary", "accent_fg", "bg_sidebar"),
            (self.btn_verificar, "btn_secondary_bg", "btn_secondary_fg", "bg_sidebar"),
            (self.btn_cancelar, "btn_danger", "accent_fg", "bg_sidebar"),
        ])

        self.btn_theme = tk.Button(
            side_bottom,
            text="Tema: Oscuro" if self.theme_var.get() == "light" else "Tema: Claro",
            command=self._toggle_theme,
            bg=t["btn_secondary_bg"],
            fg=t["btn_secondary_fg"],
            width=196,
            height=32,
            font=("Segoe UI", 9, "bold"),
        )
        self.btn_theme.pack()
        self._themed_buttons.append((self.btn_theme, "btn_secondary_bg", "btn_secondary_fg", "bg_sidebar"))

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

        self.lbl_queue_badge = tk.Label(topbar, text="Cola: 0  |  Omitidos: 0", font=("Segoe UI", 9), bg=t["bg_surface"], fg=t["fg_muted"])
        self.lbl_queue_badge.pack(side=tk.RIGHT, padx=20)
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

        chk_rec = tk.Checkbutton(
            acciones,
            text="Buscar recursivo",
            variable=self.var_recursivo,
            bg=t["bg_surface"],
            fg=t["fg_secondary"],
            activebackground=t["bg_surface"],
            activeforeground=t["fg_primary"],
            selectcolor=t["bg_input"],
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
        chk_sub = tk.Checkbutton(r_sub, text="Subcarpeta:", variable=self.var_subcarpeta, bg=t["bg_surface"], fg=t["fg_secondary"], activebackground=t["bg_surface"], activeforeground=t["fg_primary"], selectcolor=t["bg_input"])
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
        self.cb_decod.pack(side=tk.LEFT)

        r_chk = tk.Frame(col_enc, bg=t["bg_surface"])
        r_chk.pack(fill=tk.X, pady=(2, 0))
        self._themed_frames.append((r_chk, "bg_surface", None))
        chk_meta = tk.Checkbutton(r_chk, text="Limpiar metadatos al finalizar", variable=self.var_eliminar_metadatos, bg=t["bg_surface"], fg=t["fg_secondary"], activebackground=t["bg_surface"], activeforeground=t["fg_primary"], selectcolor=t["bg_input"])
        chk_meta.pack(side=tk.LEFT, padx=(0, 14))
        self._themed_checks.append((chk_meta, "bg_surface", "fg_secondary"))

        chk_ext = tk.Checkbutton(r_chk, text="Incluir subs externos (.srt)", variable=self.var_buscar_subtitulos_externos, bg=t["bg_surface"], fg=t["fg_secondary"], activebackground=t["bg_surface"], activeforeground=t["fg_primary"], selectcolor=t["bg_input"])
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
        self.activity_tree.heading("estado", text="Estado")
        self.activity_tree.heading("video", text="Video")
        self.activity_tree.heading("accion", text="Proceso")
        self.activity_tree.heading("detalle", text="Detalle")

        self.activity_tree.column("estado", width=105, minwidth=95, anchor=tk.CENTER, stretch=False)
        self.activity_tree.column("video", width=290, minwidth=180, anchor=tk.W, stretch=True)
        self.activity_tree.column("accion", width=175, minwidth=145, anchor=tk.CENTER, stretch=False)
        self.activity_tree.column("detalle", width=340, minwidth=200, anchor=tk.W, stretch=True)

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

    def _ffprobe_info(self, filepath):
        filepath = os.path.abspath(os.path.normpath(filepath))
        if hasattr(self, "ffprobe_cache") and filepath in self.ffprobe_cache:
            return self.ffprobe_cache[filepath]

        if len(filepath) > 260 and not filepath.startswith("\\\\?\\"):
            filepath = "\\\\?\\" + filepath

        cmd = [self.ffprobe_path, "-v", "error", "-print_format", "json", "-show_streams", filepath]
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
        if result.returncode != 0:
            self._log_message(f"Error ffprobe: {result.stderr[:220]}")
            return None

        try:
            data = json.loads(result.stdout)
            if "streams" not in data:
                return None
            if getattr(self, "var_buscar_subtitulos_externos", None) is None or self.var_buscar_subtitulos_externos.get():
                self._attach_external_subtitles(filepath, data)
            if hasattr(self, "ffprobe_cache"):
                self.ffprobe_cache[filepath] = data
            return data
        except json.JSONDecodeError:
            return None

    def _attach_external_subtitles(self, filepath, data):
        if not data or "streams" not in data:
            return
        data["streams"] = [s for s in data["streams"] if not s.get("is_external")]
        ext_subs = buscar_subtitulos_externos(filepath)
        if not ext_subs:
            return
        max_idx = max([s.get("index", 0) for s in data["streams"]], default=0)
        for i, sub in enumerate(ext_subs, start=1):
            stream_idx = max_idx + 100 + i
            ext_stream = {
                "index": stream_idx,
                "codec_type": "subtitle",
                "codec_name": "subrip",
                "is_external": True,
                "external_path": sub["path"],
                "tags": {
                    "language": sub["lang_code"],
                    "title": f"[EXT] {sub['lang_label']}",
                },
                "disposition": {
                    "default": 0,
                    "forced": 1 if "forzado" in sub["lang_label"].lower() else 0,
                }
            }
            data["streams"].append(ext_stream)

    def _invalidate_file_cache(self, filepath):
        if not hasattr(self, "ffprobe_cache"):
            return
        filepath_norm = os.path.abspath(os.path.normpath(filepath))
        if filepath_norm in self.ffprobe_cache:
            del self.ffprobe_cache[filepath_norm]

        path_obj = Path(filepath_norm)
        ext = path_obj.suffix
        if ext != ext.lower():
            lower_norm = os.path.abspath(os.path.normpath(path_obj.with_suffix(ext.lower())))
            if lower_norm in self.ffprobe_cache:
                del self.ffprobe_cache[lower_norm]

    def _get_language_signature(self, info):
        if not info or "streams" not in info:
            return ((), ())
        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
        audio_langs = tuple((s.get("tags") or {}).get("language", "und").lower() for s in audio_streams)
        sub_langs = tuple((s.get("tags") or {}).get("language", "und").lower() for s in subtitle_streams)
        return (audio_langs, sub_langs)

    def _format_language_summary(self, langs, max_items=5):
        if not langs:
            return "NINGUNO"
        unicos = list(dict.fromkeys(l.upper() for l in langs if l))
        if not unicos:
            return "NINGUNO"
        if len(unicos) <= max_items:
            return ", ".join(unicos)
        visibles = ", ".join(unicos[:max_items])
        restantes = len(unicos) - max_items
        return f"{visibles} (+{restantes} más)"

    def _find_compatible_signature(self, firma):
        if hasattr(self, "combinaciones_por_grupo") and firma in self.combinaciones_por_grupo:
            return firma
        return None

    def _check_ffmpeg_on_startup(self):
        if not (self.ffmpeg_path and os.path.exists(self.ffmpeg_path)):
            self.ffmpeg_path = resolve_app_binary("ffmpeg.exe")
        if not (self.ffprobe_path and os.path.exists(self.ffprobe_path)):
            self.ffprobe_path = resolve_app_binary("ffprobe.exe")

        if os.path.exists(self.ffmpeg_path) and os.path.exists(self.ffprobe_path):
            self._update_config()
            return

        messagebox.showwarning(
            "FFmpeg/FFprobe no encontrados",
            "No se detectaron ffmpeg.exe y ffprobe.exe automáticamente.\n\n"
            "Puedes colocarlos en la carpeta 'tools/' junto a VW para modo portátil o seleccionarlos manualmente.",
        )
        self.change_ffmpeg_path()
        if not os.path.exists(self.ffprobe_path):
            self.change_ffprobe_path()

    def _on_gpu_change(self):
        preset_actual = self.preset_var.get()
        nuevo = obtener_preset_valido(preset_actual, self.gpu_acel_var.get())
        if nuevo != preset_actual:
            self.preset_var.set(nuevo)

    def _is_nvidia_available(self):
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

            encoders_proc = subprocess.run(
                [self.ffmpeg_path, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=5
            )
            if encoders_proc.returncode != 0 or encoder not in encoders_proc.stdout:
                return False, "No soportado por FFmpeg"

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

    def _start_gpu_detection(self):
        self._log_message("Iniciando detección de hardware gráfico...")
        threading.Thread(target=self._detect_gpus_worker, daemon=True).start()

    def _detect_gpus_worker(self):
        nv_ok, nv_msg = self._check_encoder("h264_nvenc")
        intel_ok, intel_msg = self._check_encoder("h264_qsv")
        amd_ok, amd_msg = self._check_encoder("h264_amf")

        self.gpus_status = {
            "nvidia": (nv_ok, nv_msg),
            "intel": (intel_ok, intel_msg),
            "amd": (amd_ok, amd_msg)
        }

        self._log_message(f"Detección GPU - NVIDIA NVENC: {'OK' if nv_ok else 'No disponible (' + nv_msg + ')'}")
        self._log_message(f"Detección GPU - Intel QSV: {'OK' if intel_ok else 'No disponible (' + intel_msg + ')'}")
        self._log_message(f"Detección GPU - AMD AMF: {'OK' if amd_ok else 'No disponible (' + amd_msg + ')'}")

        self.root.after(0, self._update_gpu_selector_ui)

    def _update_gpu_selector_ui(self):
        values = []
        available_keys = []
        self.gpu_availability = {}
        for gpu_key, display_name in [("nvidia", "NVIDIA (NVENC)"), ("intel", "Intel (QSV)"), ("amd", "AMD (AMF)")]:
            is_ok = self.gpus_status.get(gpu_key, (False, ""))[0]
            self.gpu_availability[gpu_key] = is_ok
            if is_ok:
                values.append(display_name)
                available_keys.append(gpu_key)
                self.gpu_map_display_to_val[display_name] = gpu_key

        if not values:
            self.cb_gpu.config(values=["Sin GPU disponible"], state="disabled")
            self.cb_gpu.set("Sin GPU disponible")
            return

        self.cb_gpu.config(values=values, state="readonly")
        if self.gpu_acel_var.get() not in available_keys:
            self.gpu_acel_var.set(available_keys[0])
        self._sync_gpu_combobox()

    def _sync_gpu_combobox(self):
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
            self._sync_gpu_combobox()
            return

        self.gpu_acel_var.set(gpu_key)
        self._on_gpu_change()

    def _show_track_selector(self, info, filename):
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
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)

        resultado = {"ok": False, "audio": None, "subtitle": "NINGUNO", "aplicar_todos": False}

        tk.Label(dialog, text=f"Archivo: {os.path.basename(filename)}", font=("Segoe UI", 10, "bold")).pack(pady=(10, 6))

        btns = tk.Frame(dialog)
        btns.pack(side=tk.BOTTOM, pady=10)

        apply_all = tk.BooleanVar(value=False)
        tk.Checkbutton(dialog, text="Aplicar seleccion a todos los archivos", variable=apply_all).pack(side=tk.BOTTOM, pady=6)

        body_container = tk.Frame(dialog)
        body_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10)

        canvas = tk.Canvas(body_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        body = tk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=body, anchor="nw")

        def _actualizar_scroll_pistas(event=None):
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if not bbox:
                return
            content_height = bbox[3] - bbox[1]
            canvas_height = canvas.winfo_height()
            canvas.configure(scrollregion=(0, 0, bbox[2], content_height))
            if content_height > canvas_height and canvas_height > 1:
                if not scrollbar.winfo_ismapped():
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                if scrollbar.winfo_ismapped():
                    scrollbar.pack_forget()
                canvas.yview_moveto(0)

        body.bind("<Configure>", _actualizar_scroll_pistas)

        def _on_canvas_configure(e):
            canvas.itemconfig(canvas_window, width=e.width)
            _actualizar_scroll_pistas()

        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            bbox = canvas.bbox("all")
            if not bbox:
                return
            content_height = bbox[3] - bbox[1]
            canvas_height = canvas.winfo_height()
            if content_height <= canvas_height:
                return
            delta = int(-1 * (event.delta / 120))
            canvas.yview_scroll(delta, "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        dialog.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget == dialog else None, add="+")

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

        dialog.after(50, _actualizar_scroll_pistas)

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
            if self.cancelar_procesamiento:
                return resultado

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
                if self.cancelar_procesamiento:
                    return resultado
                return self._show_track_selector(info, filename)
        return resultado

    def _show_combination_selector(self, info, filename, subgrupo_label=None, modo_previo=False):
        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]

        if not audio_streams and not subtitle_streams:
            return {"ok": True, "combinaciones": [], "aplicar_todos": True if modo_previo else False}

        dialog = tk.Toplevel(self.root)
        sg_title = ""
        if subgrupo_label:
            # Mantener el título conciso para no desplazar el nombre del archivo
            sg_title = f" - {subgrupo_label.split(' | ')[0]}"
        dialog.title(f"Versiones a generar{sg_title} - {os.path.basename(filename)}")
        dialog.geometry("900x620")
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)

        dialog.update_idletasks()
        try:
            x = self.root.winfo_x() + max(0, (self.root.winfo_width() - 900) // 2)
            y = self.root.winfo_y() + max(0, (self.root.winfo_height() - 620) // 2)
            dialog.geometry(f"900x620+{x}+{y}")
        except Exception:
            pass

        t = get_theme(self.theme_var.get())
        dialog.configure(bg=t["bg_app"])
        dialog._vw_themed = True
        resultado = {"ok": False, "combinaciones": [], "aplicar_todos": False}
        combinaciones = []

        hdr_card = tk.Frame(dialog, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        hdr_card.pack(fill=tk.X, padx=16, pady=(14, 10))
        hdr_in = tk.Frame(hdr_card, bg=t["bg_surface"])
        hdr_in.pack(fill=tk.X, padx=14, pady=10)
        tk.Label(hdr_in, text="VW", font=("Segoe UI", 10, "bold"), bg=t["accent"], fg="#FFFFFF", padx=7, pady=2).pack(side=tk.LEFT)
        hdr_txt = tk.Frame(hdr_in, bg=t["bg_surface"])
        hdr_txt.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        if subgrupo_label:
            tk.Label(hdr_txt, text=subgrupo_label, font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["accent"], anchor=tk.W, wraplength=760, justify=tk.LEFT).pack(anchor=tk.W)
            tk.Label(hdr_txt, text="Marca las pistas deseadas y pulsa Aceptar (o agrégalas como versiones múltiples).", font=("Segoe UI", 8), bg=t["bg_surface"], fg=t["fg_muted"]).pack(anchor=tk.W)
        else:
            tk.Label(hdr_txt, text="Marca las pistas deseadas y pulsa Aceptar", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W)

        # Empaquetar la barra inferior primero para garantizar que los botones Aceptar/Cancelar nunca queden fuera de pantalla
        bottom = tk.Frame(dialog, bg=t["bg_app"])
        bottom.pack(side=tk.BOTTOM, pady=(4, 14))

        apply_all = tk.BooleanVar(value=True if modo_previo else False)
        chk_text = "Aplicar esta configuración a todos los archivos de este subgrupo" if modo_previo else "Aplicar esta configuración a todos los similares (mismo subgrupo)"
        tk.Checkbutton(
            dialog,
            text=chk_text,
            variable=apply_all,
            bg=t["bg_app"],
            fg=t["fg_secondary"],
            activebackground=t["bg_app"],
            activeforeground=t["fg_primary"],
            selectcolor=t["bg_input"],
        ).pack(side=tk.BOTTOM, pady=(4, 2))

        body = tk.Frame(dialog, bg=t["bg_app"])
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        left = tk.Frame(body, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        tk.Label(left, text="Pistas disponibles", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W, padx=14, pady=(12, 8))
        tk.Frame(left, height=1, bg=t["border"]).pack(fill=tk.X, padx=14, pady=(0, 8))

        var_hardsub = tk.BooleanVar(value=False)
        cb_hardsub = tk.Checkbutton(
            left,
            text="Hacer hardsub (Incrustar)",
            variable=var_hardsub,
            font=("Segoe UI", 9, "bold"),
            bg=t["bg_surface"],
            fg=t["danger"],
            activebackground=t["bg_surface"],
            activeforeground=t["danger"],
            selectcolor=t["bg_input"],
            state=tk.DISABLED,
        )
        cb_hardsub.pack(side=tk.BOTTOM, anchor=tk.W, padx=14, pady=(6, 10))

        tracks_container = tk.Frame(left, bg=t["bg_surface"])
        tracks_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10)

        canvas = tk.Canvas(tracks_container, bg=t["bg_surface"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(tracks_container, orient="vertical", command=canvas.yview, style="Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollable_frame = tk.Frame(canvas, bg=t["bg_surface"])
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _actualizar_scroll_combos(event=None):
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if not bbox:
                return
            content_height = bbox[3] - bbox[1]
            canvas_height = canvas.winfo_height()
            canvas.configure(scrollregion=(0, 0, bbox[2], content_height))
            if content_height > canvas_height and canvas_height > 1:
                if not scrollbar.winfo_ismapped():
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                if scrollbar.winfo_ismapped():
                    scrollbar.pack_forget()
                canvas.yview_moveto(0)

        scrollable_frame.bind("<Configure>", _actualizar_scroll_combos)

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
            _actualizar_scroll_combos()

        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            bbox = canvas.bbox("all")
            if not bbox:
                return
            content_height = bbox[3] - bbox[1]
            canvas_height = canvas.winfo_height()
            if content_height <= canvas_height:
                return
            delta = int(-1 * (event.delta / 120))
            canvas.yview_scroll(delta, "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        dialog.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget == dialog else None, add="+")

        audio_vars = []
        sub_vars = []

        es_hdr = _video_es_hdr(info)

        def actualizar_estado_hardsub():
            aud_sel = [s for v, s in audio_vars if v.get()]
            sub_sel = [s for v, s in sub_vars if v.get()]
            if es_hdr:
                var_hardsub.set(False)
                cb_hardsub.config(state=tk.DISABLED, text="Hacer hardsub (Desactivado: video HDR)")
            elif len(aud_sel) == 1 and len(sub_sel) == 1:
                sub_codec = (sub_sel[0].get("codec_name") or "").lower()
                if sub_codec in BITMAP_SUB_CODECS:
                    var_hardsub.set(False)
                    cb_hardsub.config(state=tk.DISABLED, text="Hacer hardsub (Desactivado: subtítulo bitmap)")
                else:
                    cb_hardsub.config(state=tk.NORMAL, text="Hacer hardsub (Incrustar)")
                    var_hardsub.set(True)
            else:
                var_hardsub.set(False)
                cb_hardsub.config(state=tk.DISABLED, text="Hacer hardsub (Incrustar)")

        tk.Label(scrollable_frame, text="Audio", bg=t["bg_surface"], fg=t["success"], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=6, pady=(6, 2))
        for i, s in enumerate(audio_streams):
            tags = s.get("tags") or {}
            title = tags.get("title") or f"Audio {i + 1}"
            lang = tags.get("language", "und")
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_: actualizar_estado_hardsub())
            audio_vars.append((var, s))
            tk.Checkbutton(scrollable_frame, text=f"{title} ({lang})", variable=var, anchor=tk.W, bg=t["bg_surface"], fg=t["fg_primary"], activebackground=t["bg_surface"], activeforeground=t["fg_primary"], selectcolor=t["bg_input"]).pack(fill=tk.X, padx=8, pady=2)

        tk.Label(scrollable_frame, text="Subtítulos", bg=t["bg_surface"], fg=t["accent"], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=6, pady=(8, 2))
        for i, s in enumerate(subtitle_streams):
            tags = s.get("tags") or {}
            title = tags.get("title") or f"Sub {i + 1}"
            lang = tags.get("language", "und")
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_: actualizar_estado_hardsub())
            sub_vars.append((var, s))
            tk.Checkbutton(scrollable_frame, text=f"{title} ({lang})", variable=var, anchor=tk.W, bg=t["bg_surface"], fg=t["fg_primary"], activebackground=t["bg_surface"], activeforeground=t["fg_primary"], selectcolor=t["bg_input"]).pack(fill=tk.X, padx=8, pady=2)

        dialog.after(50, _actualizar_scroll_combos)

        right = tk.Frame(body, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        tk.Label(right, text="Versiones a generar", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W, padx=14, pady=(12, 8))
        tk.Frame(right, height=1, bg=t["border"]).pack(fill=tk.X, padx=14, pady=(0, 8))

        def refresh():
            lst.delete(0, tk.END)
            for i, combo in enumerate(combinaciones):
                suffix = " (Hardsub)" if combo.get("hardsub") else ""
                lst.insert(tk.END, f"{i + 1}. {combo['label']}{suffix}")

        def agregar(mostrar_alerta=True):
            aud_sel = [s for var, s in audio_vars if var.get()]
            sub_sel = [s for var, s in sub_vars if var.get()]
            if not aud_sel and not sub_sel:
                if mostrar_alerta:
                    messagebox.showwarning("Sin seleccion", "Selecciona al menos una pista", parent=dialog)
                return False

            audio_indices = [s["index"] for s in aud_sel]
            sub_indices = [s["index"] for s in sub_sel]
            audio_ids = [obtener_identificador_pista(s) for s in aud_sel]
            sub_ids = [obtener_identificador_pista(s) for s in sub_sel]

            audio_langs = [(s.get("tags") or {}).get("language", "und").upper() for s in aud_sel]
            sub_langs = [(s.get("tags") or {}).get("language", "und").upper() for s in sub_sel]

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
            return True

        def quitar():
            sel = lst.curselection()
            if sel:
                del combinaciones[sel[0]]
                refresh()

        bt = tk.Frame(right, bg=t["bg_surface"])
        bt.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(6, 12))
        tk.Button(bt, text="Agregar versión adicional", command=agregar, bg=t["btn_success"], fg="white").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(bt, text="Quitar", command=quitar, bg=t["btn_danger"], fg="white").pack(side=tk.LEFT)

        lst = tk.Listbox(
            right,
            font=("Consolas", 9),
            bg=t["bg_subtle"],
            fg=t["fg_primary"],
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
            highlightthickness=1,
            highlightbackground=t["border"],
            relief=tk.FLAT,
        )
        lst.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=14, pady=(0, 4))

        def aceptar():
            aud_sel = [s for var, s in audio_vars if var.get()]
            sub_sel = [s for var, s in sub_vars if var.get()]
            if aud_sel or sub_sel:
                agregar(mostrar_alerta=False)

            if not combinaciones:
                messagebox.showwarning("Sin pistas seleccionadas", "Selecciona al menos una pista de audio o subtítulo antes de aceptar.", parent=dialog)
                return

            resultado["ok"] = True
            resultado["combinaciones"] = list(combinaciones)
            resultado["aplicar_todos"] = apply_all.get()
            dialog.destroy()

        tk.Button(bottom, text="Aceptar", command=aceptar, bg="#2D9CDB", fg="white", width=14).pack(side=tk.LEFT, padx=6)
        tk.Button(bottom, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=14).pack(side=tk.LEFT, padx=6)

        def on_close():
            aud_sel = [s for var, s in audio_vars if var.get()]
            sub_sel = [s for var, s in sub_vars if var.get()]
            if not combinaciones and (aud_sel or sub_sel):
                if messagebox.askyesno(
                    "Aplicar selección",
                    "Has marcado pistas para este video.\n\n¿Deseas aplicar esta selección y procesarlo?",
                    parent=dialog
                ):
                    aceptar()
                    return
            elif combinaciones:
                if messagebox.askyesno(
                    "Procesar versiones",
                    f"Tienes {len(combinaciones)} versión(es) configurada(s).\n\n¿Deseas procesar estas versiones?",
                    parent=dialog
                ):
                    resultado["ok"] = True
                    resultado["combinaciones"] = list(combinaciones)
                    resultado["aplicar_todos"] = apply_all.get()
                    dialog.destroy()
                    return
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close)
        dialog.bind("<Return>", lambda e: aceptar() if (e.widget == dialog or not isinstance(e.widget, tk.Button)) else None)

        dialog.wait_window()
        if not resultado["ok"]:
            if self.cancelar_procesamiento or modo_previo:
                return resultado

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
                self._clear_subgroups()
                resultado["ok"] = False
            elif ans is False:
                resultado["ok"] = False
            else:
                if self.cancelar_procesamiento:
                    return resultado
                return self._show_combination_selector(info, filename, subgrupo_label)
        return resultado

    def _get_combinations_to_build(self, info, filename):
        if self.cancelar_procesamiento:
            return None

        firma = self._get_language_signature(info)

        signature_match = self._find_compatible_signature(firma)
        if signature_match:
            self._log_message(f"  -> Aplicando configuración previamente guardada para el grupo de idiomas.")
            config_grupo = self.combinaciones_por_grupo[signature_match]
            combos = []
            for c in config_grupo:
                if self.cancelar_procesamiento:
                    return None
                audio_indices = [encontrar_pista_por_identificador(info["streams"], ident, "audio") for ident in c["audio_identifiers"]]
                sub_indices = [encontrar_pista_por_identificador(info["streams"], ident, "subtitle") for ident in c["sub_identifiers"] if ident != "NINGUNO"]

                audio_indices = [x for x in audio_indices if x is not None]
                sub_indices = [x for x in sub_indices if x is not None]

                combos.append({
                    "audio_indices": audio_indices,
                    "sub_indices": sub_indices,
                    "audio_identifiers": c["audio_identifiers"],
                    "sub_identifiers": c["sub_identifiers"],
                    "label": c["label"],
                    "hardsub": c["hardsub"]
                })
            if combos:
                return combos

        if self.cancelar_procesamiento:
            return None

        subgrupo_num = self.subgrupos.get(firma, 1)
        audio_langs_str = self._format_language_summary(firma[0])
        sub_langs_str = self._format_language_summary(firma[1])
        subgrupo_label = f"Subgrupo {subgrupo_num} (Audio: {audio_langs_str} | Subs: {sub_langs_str})"

        self._log_message(f"  -> Abriendo selección de versiones para el {subgrupo_label}...")

        q = queue.Queue()
        self.msg_queue.put(("SELECTOR_COMBINACIONES", info, filename, subgrupo_label, q))
        try:
            r = q.get(timeout=300)
        except queue.Empty:
            return None

        if self.cancelar_procesamiento or not r.get("ok") or not r.get("combinaciones"):
            return None

        if r.get("aplicar_todos"):
            if hasattr(self, "combinaciones_por_grupo"):
                self.combinaciones_por_grupo[firma] = [
                    {
                        "audio_identifiers": c.get("audio_identifiers", []),
                        "sub_identifiers": c.get("sub_identifiers", []),
                        "label": c["label"],
                        "hardsub": c.get("hardsub", False),
                    }
                    for c in r["combinaciones"]
                ]

        return r["combinaciones"]

    def _build_combinations(self, input_file, output_dir, info, combinaciones, errores):
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
        video_stem = Path(input_file).stem

        ok = 0
        fail = 0
        limpiar_meta = bool(self.var_eliminar_metadatos.get())
        meta_args = list(STRIP_METADATA_ARGS) if limpiar_meta else []

        for i, combo in enumerate(combinaciones, 1):
            if self.cancelar_procesamiento:
                break
            audio_indices = combo.get("audio_indices", [])
            sub_indices = combo.get("sub_indices", [])
            label = combo.get("label", "VERSION")

            out_dir = Path(output_dir)
            if self.var_subcarpeta.get():
                patron = self._resolve_subfolder_pattern(input_file, info, label, audio_indices, sub_indices)
                out_dir = out_dir / Path(patron)

            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"{video_stem}.mp4"
            self._invalidate_file_cache(output_path)

            usar_hardsub = bool(combo.get("hardsub"))
            if usar_hardsub:
                if _video_es_hdr(info):
                    self._log_message(f"  -> Aviso: Hardsub desactivado en '{label}' (video HDR; se hará remux sin pérdida para proteger el color).")
                    usar_hardsub = False
                elif sub_indices:
                    sub_obj = next((st for st in subtitle_streams if st.get("index") == sub_indices[0]), None)
                    if sub_obj and (sub_obj.get("codec_name") or "").lower() in BITMAP_SUB_CODECS:
                        self._log_message(f"  -> Aviso: Hardsub desactivado en '{label}' (subtítulo bitmap no compatible con incrustación).")
                        usar_hardsub = False

            if usar_hardsub:
                gpu = self.gpu_acel_var.get()
                is_ok = self.gpu_availability.get(gpu, True)
                if not is_ok:
                    status = self.gpus_status.get(gpu, (False, "No disponible"))
                    err_msg = f"El codificador {gpu.upper()} no está disponible. Detalle: {status[1]}"
                    self._log_message(f"Error: {err_msg}. Saltando hardsub.")
                    self._record_activity("error", os.path.basename(input_file), f"Hardsub ({label})", err_msg, item_key=f"combo:{output_path}")
                    errores.append((input_file, f"Versión '{label}': {err_msg}"))
                    fail += 1
                    continue

                audio_idx = audio_indices[0] if audio_indices else None
                sub_idx = sub_indices[0] if sub_indices else None
                temp_subtitle_path = None
                temp_utf8_sub_path = None

                try:
                    if sub_idx is not None:
                        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False, encoding="utf-8")
                        temp_subtitle_path = tf.name
                        tf.close()

                        sub_stream_obj = next((st for st in info["streams"] if st.get("index") == sub_idx), None)
                        if sub_stream_obj and sub_stream_obj.get("is_external"):
                            ext_file = sub_stream_obj.get("external_path")
                            actual_sub_path, temp_utf8_sub_path = asegurar_subtitulo_externo_utf8(ext_file)
                            extract = [self.ffmpeg_path, "-i", actual_sub_path, "-y", temp_subtitle_path]
                        else:
                            extract = [self.ffmpeg_path, "-i", input_file, "-map", f"0:{sub_idx}", "-y", temp_subtitle_path]

                        res = self._run_subprocess_cancellable(extract)
                        if res.returncode != 0:
                            err_detail = ""
                            if hasattr(res, "stderr") and res.stderr:
                                lines_err = [l.strip() for l in res.stderr.splitlines() if l.strip()]
                                if lines_err:
                                    err_detail = f" Detalle: {' '.join(lines_err[-2:])}"
                            err_msg = f"Fallo al extraer/procesar subtítulo de la versión '{label}'.{err_detail}"
                            self._log_message(err_msg)
                            self._record_activity("error", os.path.basename(input_file), f"Hardsub ({label})", err_msg, item_key=f"combo:{output_path}")
                            errores.append((input_file, f"Versión '{label}': {err_msg}"))
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
                    audio_codec_lower = str(audio_codec).lower() if audio_codec else ""
                    audio_settings = ["-c:a", "aac", "-b:a", "320k"] if audio_codec_lower in INCOMPATIBLE_MP4_AUDIO_CODECS else ["-c:a", "copy"]

                    preset = obtener_preset_valido(self.preset_var.get(), self.gpu_acel_var.get())

                    decod_val = self.decod_hw_var.get().lower()
                    hwaccel_opts = []
                    if decod_val in ("d3d11va", "dxva2") and sub_idx is None:
                        hwaccel_opts = ["-hwaccel", decod_val]

                    color_flags = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]

                    if gpu == "nvidia":
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_nvenc", "-preset", preset,
                            "-profile:v", "high", "-rc", "vbr", "-cq", "23",
                            "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *color_flags,
                            *audio_settings, *meta_args, "-movflags", "+faststart", "-y", str(output_path)
                        ]
                    elif gpu == "intel":
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_qsv", "-preset", preset,
                            "-global_quality", "23",
                            "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *color_flags,
                            *audio_settings, *meta_args, "-movflags", "+faststart", "-y", str(output_path)
                        ]
                    else:
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_amf", "-quality", preset,
                            "-rc", "vbr_peak", "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *color_flags,
                            *audio_settings, *meta_args, "-movflags", "+faststart", "-y", str(output_path)
                        ]

                    self._record_activity("procesando", os.path.basename(input_file), f"Hardsub ({label})", "Incrustando subtítulos...", item_key=f"combo:{output_path}")
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
                        carpeta_salida = output_path.parent.name or str(output_path.parent)
                        meta_txt = "Sin metadatos" if limpiar_meta else "Con metadatos"
                        self._record_activity(
                            "exito",
                            os.path.basename(input_file),
                            f"Hardsub ({label})",
                            f"Carpeta: {carpeta_salida}/ | {meta_txt}",
                            item_key=f"combo:{output_path}",
                            log_extra={
                                "Salida": ruta_completa,
                                "Audios": audios_info,
                                "Subtítulos": subs_info,
                                "Metadatos": "Eliminados" if limpiar_meta else "Conservados",
                            },
                        )
                    else:
                        err_detail = ""
                        if hasattr(result, "stderr") and result.stderr:
                            lines_err = [l.strip() for l in result.stderr.splitlines() if l.strip()]
                            if lines_err:
                                err_detail = f" Detalle: {' '.join(lines_err[-2:])}"
                        err_msg = f"Error de FFmpeg al codificar la versión hardsub (código de salida: {result.returncode}).{err_detail}"
                        self._log_message(err_msg)
                        self._record_activity("error", os.path.basename(input_file), f"Hardsub ({label})", err_msg, item_key=f"combo:{output_path}")
                        errores.append((input_file, f"Versión '{label}': {err_msg}"))
                        fail += 1
                finally:
                    if temp_subtitle_path and os.path.exists(temp_subtitle_path):
                        try:
                            os.unlink(temp_subtitle_path)
                        except Exception:
                            pass
                    if temp_utf8_sub_path and os.path.exists(temp_utf8_sub_path):
                        try:
                            os.unlink(temp_utf8_sub_path)
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
                    self._log_message(f"Advertencia: {excluidos} subtítulos bitmap/no texto excluidos")

                video_streams = [s for s in info["streams"] if s.get("codec_type") == "video"]
                main_video_streams = [s for s in video_streams if not s.get("disposition", {}).get("attached_pic")]
                if not main_video_streams:
                    main_video_streams = video_streams

                ext_inputs = {}
                temp_utf8_files = []
                next_in_idx = 1
                for idx in sub_incluir:
                    s = next((st for st in subtitle_streams if st["index"] == idx), None)
                    if s and s.get("is_external"):
                        ext_path = s["external_path"]
                        if ext_path not in ext_inputs:
                            actual_path, temp_path = asegurar_subtitulo_externo_utf8(ext_path)
                            if temp_path:
                                temp_utf8_files.append(temp_path)
                            ext_inputs[ext_path] = (next_in_idx, actual_path)
                            next_in_idx += 1

                try:
                    cmd = [self.ffmpeg_path, "-i", input_file]
                    for ext_path, (in_idx, actual_path) in sorted(ext_inputs.items(), key=lambda x: x[1][0]):
                        cmd.extend(["-i", actual_path])

                    for s in main_video_streams:
                        cmd.extend(["-map", f"0:{s['index']}"])
                        if s.get("codec_name", "").lower() in ("hevc", "h265"):
                            cmd.extend(["-tag:v", "hvc1"])

                    cmd.extend(["-c:v", "copy"])

                    for idx_pos, idx in enumerate(audio_indices):
                        cmd.extend(["-map", f"0:{idx}"])
                        s = next((st for st in info["streams"] if st.get("index") == idx), None)
                        acodec = s.get("codec_name", "").lower() if s else ""
                        if acodec in INCOMPATIBLE_MP4_AUDIO_CODECS:
                            cmd.extend([f"-c:a:{idx_pos}", "aac", f"-b:a:{idx_pos}", "320k"])
                        else:
                            cmd.extend([f"-c:a:{idx_pos}", "copy"])

                    if not audio_indices:
                        cmd.extend(["-c:a", "copy"])

                    for out_sub_pos, idx in enumerate(sub_incluir):
                        s = next((st for st in subtitle_streams if st["index"] == idx), None)
                        if s and s.get("is_external"):
                            in_idx = ext_inputs[s["external_path"]][0]
                            cmd.extend(["-map", f"{in_idx}:0"])
                        else:
                            cmd.extend(["-map", f"0:{idx}"])
                        if s and not limpiar_meta:
                            tags_s = s.get("tags") or {}
                            lang_s = tags_s.get("language")
                            if lang_s:
                                cmd.extend([f"-metadata:s:s:{out_sub_pos}", f"language={lang_s}"])

                    if sub_incluir:
                        cmd.extend(["-c:s", "mov_text"])

                    cmd.extend([*meta_args, "-movflags", "+faststart", "-y", str(output_path)])

                    self._record_activity("procesando", os.path.basename(input_file), f"Remux ({label})", "Multiplexando pistas...", item_key=f"combo:{output_path}")
                    result = self._run_subprocess_cancellable(cmd)

                    if result.returncode != 0 and sub_incluir:
                        self._log_message("  -> Advertencia: Falló multiplexado de subtítulos en MP4. Reintentando remux sin subtítulos...")
                        cmd_fallback = [self.ffmpeg_path, "-i", input_file]
                        for s in main_video_streams:
                            cmd_fallback.extend(["-map", f"0:{s['index']}"])
                            if s.get("codec_name", "").lower() in ("hevc", "h265"):
                                cmd_fallback.extend(["-tag:v", "hvc1"])
                        cmd_fallback.extend(["-c:v", "copy"])
                        for idx_pos, idx in enumerate(audio_indices):
                            cmd_fallback.extend(["-map", f"0:{idx}"])
                            s = next((st for st in info["streams"] if st.get("index") == idx), None)
                            acodec = s.get("codec_name", "").lower() if s else ""
                            if acodec in INCOMPATIBLE_MP4_AUDIO_CODECS:
                                cmd_fallback.extend([f"-c:a:{idx_pos}", "aac", f"-b:a:{idx_pos}", "320k"])
                            else:
                                cmd_fallback.extend([f"-c:a:{idx_pos}", "copy"])
                        if not audio_indices:
                            cmd_fallback.extend(["-c:a", "copy"])
                        cmd_fallback.extend(["-sn", *meta_args, "-movflags", "+faststart", "-y", str(output_path)])
                        result = self._run_subprocess_cancellable(cmd_fallback)
                        if result.returncode == 0:
                            sub_incluir = []
                finally:
                    for tf in temp_utf8_files:
                        if tf and os.path.exists(tf):
                            try:
                                os.unlink(tf)
                            except Exception:
                                pass

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
                    carpeta_salida = output_path.parent.name or str(output_path.parent)
                    meta_txt = "Sin metadatos" if limpiar_meta else "Con metadatos"
                    self._record_activity(
                        "exito",
                        os.path.basename(input_file),
                        f"Remux ({label})",
                        f"Carpeta: {carpeta_salida}/ | {meta_txt}",
                        item_key=f"combo:{output_path}",
                        log_extra={
                            "Salida": ruta_completa,
                            "Audios": audios_info,
                            "Subtítulos": subs_info,
                            "Metadatos": "Eliminados" if limpiar_meta else "Conservados",
                        },
                    )
                else:
                    err_detail = ""
                    if hasattr(result, "stderr") and result.stderr:
                        lines = [l.strip() for l in result.stderr.splitlines() if l.strip()]
                        if lines:
                            err_detail = f" Detalle: {' '.join(lines[-2:])}"
                    err_msg = f"Error de FFmpeg al copiar/remuxear la versión (código de salida: {result.returncode}).{err_detail}"
                    self._log_message(err_msg)
                    self._record_activity("error", os.path.basename(input_file), f"Remux ({label})", err_msg, item_key=f"combo:{output_path}")
                    errores.append((input_file, f"Versión '{label}': {err_msg}"))
                    fail += 1

        return ok, fail

    def _strip_tracks_processing(self, archivo, output_dir, errores):
        if self.cancelar_procesamiento:
            return False

        info = self._ffprobe_info(archivo)
        if info is None:
            err_msg = "No se pudo leer streams con ffprobe."
            self._log_message(err_msg)
            errores.append((archivo, err_msg))
            return False

        if self.cancelar_procesamiento:
            return False

        v = sum(1 for s in info["streams"] if s.get("codec_type") == "video")
        if v < 1:
            err_msg = "El archivo no contiene ninguna pista de video."
            self._log_message(err_msg)
            errores.append((archivo, err_msg))
            return False

        combinaciones = self._get_combinations_to_build(info, archivo)
        if self.cancelar_procesamiento or combinaciones is None:
            if not self.cancelar_procesamiento:
                err_msg = "Se canceló la selección de combinaciones."
                self._log_message(err_msg)
                errores.append((archivo, err_msg))
            return False

        return self._build_combinations(archivo, output_dir, info, combinaciones, errores)

    def _clear_subgroups(self):
        if hasattr(self, "subgrupos"):
            self.subgrupos.clear()
        else:
            self.subgrupos = {}
        if hasattr(self, "combinaciones_por_grupo"):
            self.combinaciones_por_grupo.clear()
        else:
            self.combinaciones_por_grupo = {}
        self.combinaciones_a_aplicar = {"combinaciones": [], "aplicar_a_todos": False}
        self.pistas_config = {"audio_tag": None, "subtitle_tag": None, "aplicar_a_todos": False}

    def _get_subgroup_map(self, archivos):
        subgrupos_dict = {}
        subgrupo_counter = 1
        for archivo in archivos:
            info = self._ffprobe_info(archivo)
            if not info:
                continue
            firma = self._get_language_signature(info)
            if firma not in subgrupos_dict:
                subgrupos_dict[firma] = {
                    "firma": firma,
                    "num": subgrupo_counter,
                    "archivos": [archivo],
                    "sample_archivo": archivo,
                    "sample_info": info,
                }
                subgrupo_counter += 1
            else:
                subgrupos_dict[firma]["archivos"].append(archivo)
        return list(subgrupos_dict.values())

    def _preconfigure_queue_subgroups(self, archivos, output_dir=None, forzar_reconfiguracion=False):
        subgrupos_list = self._get_subgroup_map(archivos)
        if not subgrupos_list:
            self._clear_subgroups()
            return True

        if not hasattr(self, "combinaciones_por_grupo") or forzar_reconfiguracion:
            self.combinaciones_por_grupo = {}

        if not hasattr(self, "subgrupos") or forzar_reconfiguracion:
            self.subgrupos = {}
        for sg in subgrupos_list:
            self.subgrupos[sg["firma"]] = sg["num"]

        pendientes = [sg for sg in subgrupos_list if sg["firma"] not in self.combinaciones_por_grupo]
        if not pendientes:
            return True

        total_sg = len(subgrupos_list)

        for sg in pendientes:
            firma = sg["firma"]
            sample_info = sg["sample_info"]
            sample_archivo = sg["sample_archivo"]

            audio_streams = [s for s in sample_info.get("streams", []) if s.get("codec_type") == "audio"]
            subtitle_streams = [s for s in sample_info.get("streams", []) if s.get("codec_type") == "subtitle"]

            if not audio_streams and not subtitle_streams:
                self.combinaciones_por_grupo[firma] = []
                continue

            cant_archivos = len(sg["archivos"])
            txt_archivos = f"{cant_archivos} archivo" if cant_archivos == 1 else f"{cant_archivos} archivos"
            audio_langs_str = self._format_language_summary(firma[0])
            sub_langs_str = self._format_language_summary(firma[1])
            subgrupo_label = f"Subgrupo {sg['num']} de {total_sg} ({txt_archivos}) | Audio: {audio_langs_str} | Subs: {sub_langs_str}"

            while True:
                r = self._show_combination_selector(
                    sample_info,
                    sample_archivo,
                    subgrupo_label=subgrupo_label,
                    modo_previo=True
                )
                if r.get("ok") and r.get("combinaciones"):
                    self.combinaciones_por_grupo[firma] = [
                        {
                            "audio_identifiers": c.get("audio_identifiers", []),
                            "sub_identifiers": c.get("sub_identifiers", []),
                            "label": c["label"],
                            "hardsub": c.get("hardsub", False),
                        }
                        for c in r["combinaciones"]
                    ]
                    break
                else:
                    if output_dir is not None:
                        ans = messagebox.askyesno(
                            "Cancelar procesamiento",
                            f"Has cancelado la configuración del {subgrupo_label}.\n\n¿Deseas cancelar el inicio del procesamiento de toda la cola?",
                            parent=self.root
                        )
                        if ans:
                            self._clear_subgroups()
                            return False
                        else:
                            ans_omitir = messagebox.askyesno(
                                "Omitir subgrupo",
                                f"¿Deseas omitir los {txt_archivos} correspondientes a este subgrupo y continuar con los demás?\n\n(Si eliges 'No', volverás a abrir la configuración de este subgrupo)",
                                parent=self.root
                            )
                            if ans_omitir:
                                self._move_to_skipped(sg["archivos"])
                                break
                            else:
                                continue
                    else:
                        self._clear_subgroups()
                        return False

        return True

    def _process_queue_worker(self, archivos, output_dir):
        self.procesando = True
        self.cancelar_procesamiento = False
        self.combinaciones_a_aplicar = {"combinaciones": [], "aplicar_a_todos": False}
        if not hasattr(self, "combinaciones_por_grupo") or not self.combinaciones_por_grupo:
            self.combinaciones_por_grupo = {}

        if not hasattr(self, "subgrupos") or not self.subgrupos:
            self.subgrupos = {}
            subgrupo_counter = 1
            for archivo in archivos:
                info = self._ffprobe_info(archivo)
                if info:
                    firma = self._get_language_signature(info)
                    if firma not in self.subgrupos:
                        self.subgrupos[firma] = subgrupo_counter
                        subgrupo_counter += 1

        ok = 0
        fail = 0
        total = len(archivos)
        errores = []
        self._log_message("===== INICIO PROCESAMIENTO =====")

        fue_cancelado = False
        archivos_exitosos = []
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._log_message("Cancelado por usuario")
                fue_cancelado = True
                break
            self.msg_queue.put(("PROGRESO", i, total))
            self._log_message(f"Archivo {i}/{total}: {os.path.basename(archivo)}")
            result = self._strip_tracks_processing(archivo, output_dir, errores)

            if self.cancelar_procesamiento:
                fue_cancelado = True
                errores = [err for err in errores if err[0] != archivo]
                break

            if isinstance(result, tuple):
                o, f = result
                if f == 0 and o > 0:
                    archivos_exitosos.append(archivo)
                ok += o
                fail += f
            elif result:
                archivos_exitosos.append(archivo)
                ok += 1
            else:
                fail += 1

        self._log_message("===== FIN PROCESAMIENTO =====")
        self.msg_queue.put(("FINALIZADO", ok, fail, errores, fue_cancelado, archivos_exitosos))
        self.procesando = False
        self.cancelar_procesamiento = False
        self._clear_subgroups()

    def process_queue(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return
        self._clear_subgroups()
        output = self.salida_var.get().strip()
        if not output:
            messagebox.showerror("Error", "Selecciona un directorio de salida")
            return
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        def callback_iniciar(archivos_validos):
            ok = self._preconfigure_queue_subgroups(archivos_validos, output_dir=output, forzar_reconfiguracion=True)
            if not ok:
                self._clear_subgroups()
                return

            archivos_a_procesar = [f for f in archivos_validos if f in set(self.lista.get(0, tk.END))]
            if not archivos_a_procesar:
                messagebox.showwarning("Cola vacía", "No quedan archivos para procesar.")
                self._clear_subgroups()
                return

            self.archivos_en_proceso = list(archivos_a_procesar)
            self._clear_log_and_progress("Preparando procesamiento de cola...")
            self._set_running_state(True)
            threading.Thread(target=self._process_queue_worker, args=(archivos_a_procesar, output), daemon=True).start()
            self._poll_ui_queue()

        self.precheck_queue("procesar_cola", archivos, output, callback_iniciar)

    def precheck_queue(self, tipo_proceso, archivos, output_dir, callback_exito):
        if tipo_proceso in ("procesar_cola",):
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                except Exception as exc:
                    messagebox.showerror("Error de carpeta de salida", f"No se puede crear el directorio de salida:\n{output_dir}\nDetalle: {exc}")
                    return
            if not os.access(output_dir, os.W_OK):
                messagebox.showerror("Error de permisos", f"El directorio de salida no tiene permisos de escritura:\n{output_dir}")
                return

        progreso = tk.Toplevel(self.root)
        progreso.title("Pre-verificando cola")
        progreso.geometry("500x140")
        progreso.transient(self.root)
        progreso.grab_set()
        self.root.attributes('-disabled', True)
        progreso.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == progreso and self.root.winfo_exists()) else None)

        progreso.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - progreso.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - progreso.winfo_height()) // 2
        progreso.geometry(f"+{x}+{y}")

        lbl = tk.Label(progreso, text="Pre-verificando archivos en la cola...", font=("Segoe UI", 10, "bold"))
        lbl.pack(pady=(18, 8))
        status = tk.Label(progreso, text="Preparando analisis...", font=("Segoe UI", 9))
        status.pack()
        pbar = ttk.Progressbar(progreso, mode="determinate", maximum=len(archivos), length=420)
        pbar.pack(pady=10)

        resultados = []

        def worker():
            infos = {}

            for i, archivo in enumerate(archivos, 1):
                status.config(text=f"{i}/{len(archivos)} - {os.path.basename(archivo)}")
                pbar["value"] = i
                progreso.update_idletasks()

                info = self._ffprobe_info(archivo)
                infos[archivo] = info

            for archivo in archivos:
                res = self._validate_file_for_precheck(archivo, tipo_proceso, output_dir, infos.get(archivo))
                resultados.append(res)

            progreso.destroy()
            self.root.after(0, lambda: self._handle_precheck_results(resultados, tipo_proceso, archivos, callback_exito))

        threading.Thread(target=worker, daemon=True).start()

    def _validate_file_for_precheck(self, archivo, tipo_proceso, output_dir, info=None):
        res = {
            "archivo": archivo,
            "basename": os.path.basename(archivo),
            "has_error": False,
            "has_warning": False,
            "errors": [],
            "warnings": []
        }

        if not os.path.exists(archivo):
            res["has_error"] = True
            res["errors"].append("El archivo no existe o la ruta no es valida.")
            return res

        if tipo_proceso in ("metadatos", "eliminar_subtitulos"):
            if not os.access(archivo, os.W_OK):
                res["has_error"] = True
                res["errors"].append("No se tiene permiso de escritura en el archivo original (necesario para modificar el archivo).")

        if info is None:
            info = self._ffprobe_info(archivo)
        if info is None:
            res["has_error"] = True
            res["errors"].append("ffprobe no pudo analizar el archivo. Podria estar corrupto o no ser soportado.")
            return res

        streams = info.get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

        if not video_streams:
            res["has_error"] = True
            res["errors"].append("El archivo no contiene ninguna pista de video.")

        if res["has_error"]:
            return res

        return res

    def _handle_precheck_results(self, resultados, tipo_proceso, archivos, callback_exito):
        con_errores = [r for r in resultados if r["has_error"]]
        con_advertencias = [r for r in resultados if r["has_warning"]]

        if not con_errores and not con_advertencias:
            callback_exito(archivos)
            return

        self._show_precheck_report(resultados, tipo_proceso, archivos, callback_exito)

    def _show_precheck_report(self, resultados, tipo_proceso, archivos, callback_exito):
        dialog = tk.Toplevel(self.root)
        dialog.title("Reporte de Pre-verificacion - VW")
        dialog.geometry("820x600")
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)
        dialog.configure(bg="#F3F7FF")

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        header = tk.Frame(dialog, bg="#1A2536", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Pre-verificacion de Archivos",
            font=("Segoe UI", 14, "bold"),
            bg="#1A2536",
            fg="#FFFFFF"
        ).pack(anchor=tk.W, padx=20, pady=(10, 2))

        tk.Label(
            header,
            text="Se han detectado posibles problemas. Elige cómo deseas proceder con la cola de procesamiento.",
            font=("Segoe UI", 9),
            bg="#1A2536",
            fg="#B0C4DE"
        ).pack(anchor=tk.W, padx=20)

        num_errors = 0
        num_warnings = 0
        for r in resultados:
            if r["has_error"]:
                num_errors += len(r["errors"])
            if r["has_warning"]:
                num_warnings += len(r["warnings"])

        btm = tk.Frame(dialog, bg="#F3F7FF")
        btm.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(5, 15))

        def cmd_continuar():
            filtrados = [r["archivo"] for r in resultados if not r["has_error"]]
            dialog.destroy()

            con_errores = [r["archivo"] for r in resultados if r["has_error"]]
            if con_errores:
                self.root.after(0, lambda: self._move_to_skipped(con_errores))

            if filtrados:
                callback_exito(filtrados)
            else:
                messagebox.showwarning("Cola vacia", "No quedan archivos validos para procesar tras excluir los errores.")

        def cmd_omitir_problemas():
            filtrados = [r["archivo"] for r in resultados if not r["has_error"] and not r["has_warning"]]
            dialog.destroy()

            con_problemas = [r["archivo"] for r in resultados if r["has_error"] or r["has_warning"]]
            if con_problemas:
                self.root.after(0, lambda: self._move_to_skipped(con_problemas))

            if filtrados:
                callback_exito(filtrados)
            else:
                messagebox.showwarning("Cola vacia", "No quedan archivos limpios sin advertencias ni errores para procesar.")

        def cmd_cancelar():
            self._clear_subgroups()
            dialog.destroy()

        btn_cancelar = tk.Button(
            btm,
            text="Cancelar",
            command=cmd_cancelar,
            bg="#95A5A6",
            fg="white",
            activebackground="#7F8C8D",
            activeforeground="white",
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_cancelar.pack(side=tk.RIGHT, padx=5)

        if num_warnings > 0 or num_errors > 0:
            btn_omitir = tk.Button(
                btm,
                text="Omitir archivos con problemas",
                command=cmd_omitir_problemas,
                bg="#F2994A",
                fg="white",
                activebackground="#D35400",
                activeforeground="white",
                relief=tk.FLAT,
                padx=15,
                pady=6,
                cursor="hand2",
                font=("Segoe UI", 9, "bold")
            )
            btn_omitir.pack(side=tk.RIGHT, padx=5)

        archivos_sin_errores = [r for r in resultados if not r["has_error"]]
        if archivos_sin_errores:
            btn_continuar = tk.Button(
                btm,
                text="Agregar de todos modos",
                command=cmd_continuar,
                bg="#27AE60",
                fg="white",
                activebackground="#219653",
                activeforeground="white",
                relief=tk.FLAT,
                padx=15,
                pady=6,
                cursor="hand2",
                font=("Segoe UI", 9, "bold")
            )
            btn_continuar.pack(side=tk.RIGHT, padx=5)

        body = tk.Frame(dialog, bg="#F3F7FF", padx=20, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        text_frame = tk.Frame(body, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5ECF9")

        log_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            bg="#FFFFFF",
            fg="#1F2A44",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame, command=log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.config(yscrollcommand=scrollbar.set)

        log_text.tag_config("title", font=("Segoe UI", 10, "bold"), spacing1=8, spacing3=2)
        log_text.tag_config("error_lbl", font=("Segoe UI", 9, "bold"), foreground="#EB5757")
        log_text.tag_config("warn_lbl", font=("Segoe UI", 9, "bold"), foreground="#F2994A")
        log_text.tag_config("detail", font=("Segoe UI", 9), foreground="#4F4F4F", lmargin1=25, lmargin2=25, spacing3=4)

        for r in resultados:
            if not r["has_error"] and not r["has_warning"]:
                continue

            log_text.insert(tk.END, f"Archivo: {r['basename']}\n", "title")

            for err in r["errors"]:
                log_text.insert(tk.END, "  [ERROR] ", "error_lbl")
                log_text.insert(tk.END, f"{err}\n", "detail")

            for warn in r["warnings"]:
                log_text.insert(tk.END, "  [ADVERTENCIA] ", "warn_lbl")
                log_text.insert(tk.END, f"{warn}\n", "detail")

        log_text.config(state=tk.DISABLED)

        summary_text = f"Resumen: {num_errors} error(es) critico(s) y {num_warnings} advertencia(s) encontrada(s)."
        lbl_summary = tk.Label(body, text=summary_text, font=("Segoe UI", 9, "bold"), bg="#F3F7FF", fg="#1F2A44", anchor=tk.W)

        if num_errors > 0:
            lbl_err_note = tk.Label(
                body,
                text="* Los archivos con errores criticos no podran ser procesados y seran excluidos si decide continuar.",
                font=("Segoe UI", 8, "italic"),
                bg="#F3F7FF",
                fg="#EB5757",
                anchor=tk.W
            )

        lbl_legend = tk.Label(
            body,
            text="• Agregar de todos modos: Procesa todos los archivos (incluyendo los que tienen advertencias).\n"
                 "• Omitir archivos con problemas: Excluye los archivos con advertencias o errores y procesa el resto.",
            font=("Segoe UI", 9, "italic"),
            bg="#F3F7FF",
            fg="#4F4F4F",
            justify=tk.LEFT,
            anchor=tk.W
        )

        lbl_legend.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 10))
        if num_errors > 0:
            lbl_err_note.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        lbl_summary.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 5))

        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def verify_queue_files(self):
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showwarning("Sin archivos", "No hay archivos cargados")
            return

        if hasattr(self, "ffprobe_cache"):
            self.ffprobe_cache.clear()

        progreso = tk.Toplevel(self.root)
        progreso.title("Analizando cola")
        progreso.geometry("500x140")
        progreso.transient(self.root)
        progreso.grab_set()
        self.root.attributes('-disabled', True)
        progreso.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == progreso and self.root.winfo_exists()) else None)

        lbl = tk.Label(progreso, text="Analizando archivos de la cola...", font=("Segoe UI", 10, "bold"))
        lbl.pack(pady=(18, 8))
        status = tk.Label(progreso, text="Preparando...", font=("Segoe UI", 9))
        status.pack()
        pbar = ttk.Progressbar(progreso, mode="determinate", maximum=len(archivos), length=420)
        pbar.pack(pady=10)

        resultados = []

        def worker():
            for i, archivo in enumerate(archivos, 1):
                status.config(text=f"{i}/{len(archivos)} - {os.path.basename(archivo)}")
                pbar["value"] = i
                progreso.update_idletasks()

                res = self._validate_file_for_precheck(archivo, "procesar_cola", None)
                resultados.append(res)

            progreso.destroy()
            self.root.after(0, lambda: self._show_verification_results(resultados))

        threading.Thread(target=worker, daemon=True).start()

    def _show_verification_results(self, resultados):
        t = get_theme(self.theme_var.get())
        win = tk.Toplevel(self.root)
        win.title("Diagnóstico de la cola - VW")
        win.geometry("980x640")
        win.minsize(820, 520)
        win.transient(self.root)
        win.configure(bg=t["bg_app"])
        win._vw_themed = True

        win.update_idletasks()
        x = self.root.winfo_x() + max(0, (self.root.winfo_width() - 980) // 2)
        y = self.root.winfo_y() + max(0, (self.root.winfo_height() - 640) // 2)
        win.geometry(f"+{x}+{y}")

        saludables = [r for r in resultados if not r["has_error"] and not r["has_warning"]]
        advertencias = [r for r in resultados if r["has_warning"] and not r["has_error"]]
        errores = [r for r in resultados if r["has_error"]]

        shell = tk.Frame(win, bg=t["bg_app"])
        shell.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(shell, width=215, bg=t["bg_sidebar"])
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Frame(shell, width=1, bg=t["border"]).pack(side=tk.LEFT, fill=tk.Y)

        brand_row = tk.Frame(sidebar, bg=t["bg_sidebar"])
        brand_row.pack(fill=tk.X, padx=16, pady=(18, 14))
        tk.Label(brand_row, text="VW", font=("Segoe UI", 11, "bold"), bg=t["accent"], fg="#FFFFFF", padx=8, pady=2).pack(side=tk.LEFT)
        brand_txt = tk.Frame(brand_row, bg=t["bg_sidebar"])
        brand_txt.pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(brand_txt, text="Diagnóstico", font=("Segoe UI", 10, "bold"), bg=t["bg_sidebar"], fg=t["fg_primary"]).pack(anchor=tk.W)
        tk.Label(brand_txt, text="Integridad de cola", font=("Segoe UI", 8), bg=t["bg_sidebar"], fg=t["fg_muted"]).pack(anchor=tk.W)

        tk.Frame(sidebar, height=1, bg=t["border"]).pack(fill=tk.X, padx=16, pady=(0, 12))
        tk.Label(sidebar, text="FILTROS", font=("Segoe UI", 8, "bold"), bg=t["bg_sidebar"], fg=t["fg_muted"]).pack(anchor=tk.W, padx=18, pady=(0, 6))

        nav_btns = {}

        def _poblar_tabla(clave):
            for k, btn in nav_btns.items():
                activo = k == clave
                btn.config(
                    bg=t["accent"] if activo else t["bg_sidebar"],
                    fg="#FFFFFF" if activo else t["fg_secondary"],
                    parent_bg=t["bg_sidebar"],
                )

            titulos = {
                "todos": "Todos los archivos",
                "saludables": "Archivos saludables",
                "advertencias": "Archivos con advertencias",
                "errores": "Errores o inaccesibles",
            }
            lbl_titulo.config(text=titulos.get(clave, "Diagnóstico"))
            tree.delete(*tree.get_children())

            if clave in ("todos", "saludables"):
                for r in saludables:
                    tree.insert("", tk.END, values=("Saludable", r["basename"], r["archivo"]), tags=("exito",))
            if clave in ("todos", "advertencias"):
                for r in advertencias:
                    det = " | ".join(r["warnings"]) if r["warnings"] else r["archivo"]
                    tree.insert("", tk.END, values=("Advertencia", r["basename"], det), tags=("aviso",))
            if clave in ("todos", "errores"):
                for r in errores:
                    det = " | ".join(r["errors"]) if r["errors"] else r["archivo"]
                    tree.insert("", tk.END, values=("Error", r["basename"], det), tags=("error",))

        filtros = [
            ("todos", f"Todos ({len(resultados)})"),
            ("saludables", f"Saludables ({len(saludables)})"),
            ("advertencias", f"Advertencias ({len(advertencias)})"),
            ("errores", f"Errores ({len(errores)})"),
        ]
        for key, txt in filtros:
            b = tk.Button(
                sidebar,
                text=txt,
                command=lambda k=key: _poblar_tabla(k),
                bg=t["bg_sidebar"],
                fg=t["fg_secondary"],
                width=183,
                height=32,
                align="left",
                padx=12,
                font=("Segoe UI", 9, "bold"),
            )
            b.pack(padx=16, pady=2)
            nav_btns[key] = b

        side_btm = tk.Frame(sidebar, bg=t["bg_sidebar"])
        side_btm.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(8, 16))
        tk.Frame(side_btm, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 12))
        tk.Button(
            side_btm,
            text="Cerrar",
            command=win.destroy,
            bg=t["btn_primary"],
            fg="#FFFFFF",
            width=183,
            height=34,
            font=("Segoe UI", 9, "bold"),
        ).pack()

        content = tk.Frame(shell, bg=t["bg_app"])
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        topbar = tk.Frame(content, height=52, bg=t["bg_surface"])
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Frame(content, height=1, bg=t["border"]).pack(fill=tk.X)

        lbl_titulo = tk.Label(topbar, text="Todos los archivos", font=("Segoe UI", 11, "bold"), bg=t["bg_surface"], fg=t["fg_primary"])
        lbl_titulo.pack(side=tk.LEFT, padx=20)
        tk.Label(
            topbar,
            text=f"Saludables: {len(saludables)}  |  Advertencias: {len(advertencias)}  |  Errores: {len(errores)}",
            font=("Segoe UI", 9),
            bg=t["bg_surface"],
            fg=t["fg_muted"],
        ).pack(side=tk.RIGHT, padx=20)

        card = tk.Frame(content, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        card.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        tree_frame = tk.Frame(card, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"], highlightcolor=t["border"])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        tree = ttk.Treeview(tree_frame, columns=("estado", "archivo", "detalle"), show="headings", style="Activity.Treeview", takefocus=False)
        tree.bind("<FocusIn>", lambda e: win.focus_set())
        tree.heading("estado", text="Estado")
        tree.heading("archivo", text="Archivo")
        tree.heading("detalle", text="Ruta / Detalle")
        tree.column("estado", width=105, minwidth=95, anchor=tk.CENTER, stretch=False)
        tree.column("archivo", width=260, minwidth=160, anchor=tk.W, stretch=True)
        tree.column("detalle", width=360, minwidth=200, anchor=tk.W, stretch=True)

        tree.tag_configure("exito", foreground=t["success"], background=t["success_bg"])
        tree.tag_configure("aviso", foreground=t["warning"], background=t["warning_bg"])
        tree.tag_configure("error", foreground=t["danger"], background=t["danger_bg"])

        def _limpiar_sel(event):
            if event.widget is tree:
                if not tree.identify_row(event.y):
                    tree.selection_remove(tree.selection())
            elif tree.selection():
                tree.selection_remove(tree.selection())

        win.bind("<Button-1>", _limpiar_sel, add="+")

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scr = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview, style="Vertical.TScrollbar")
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scr.set)

        _poblar_tabla("todos")

    def _strip_file_metadata(self, video_file, errores=None):
        video_file = Path(video_file)
        temp_output = video_file.parent / f"temp_{video_file.name}"
        info = self._ffprobe_info(video_file)

        is_mp4 = video_file.suffix.lower() in (".mp4", ".m4v")
        audio_args = ["-c:a", "copy"]
        sub_args = ["-c:s", "copy"]

        if is_mp4 and info and "streams" in info:
            audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
            if any(s.get("codec_name", "").lower() in INCOMPATIBLE_MP4_AUDIO_CODECS for s in audio_streams):
                audio_args = ["-c:a", "aac", "-b:a", "320k"]
            sub_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
            if sub_streams:
                if any(s.get("codec_name", "").lower() in BITMAP_SUB_CODECS for s in sub_streams):
                    sub_args = ["-sn"]
                else:
                    sub_args = ["-c:s", "mov_text"]

        mp4_faststart = ["-movflags", "+faststart"] if is_mp4 else []

        cmd = [
            self.ffmpeg_path,
            "-i",
            str(video_file),
            "-map",
            "0:V?",
            "-map",
            "0:a?",
        ]
        if sub_args != ["-sn"]:
            cmd.extend(["-map", "0:s?"])

        cmd.extend(["-c:v", "copy", *audio_args, *sub_args, *STRIP_METADATA_ARGS, *mp4_faststart, "-y", str(temp_output)])

        try:
            res = self._run_subprocess_cancellable(cmd, stdout_devnull=True)
            if res.returncode != 0:
                cmd_fb = [
                    self.ffmpeg_path,
                    "-i",
                    str(video_file),
                    "-map",
                    "0:V?",
                    "-map",
                    "0:a?",
                    "-c:v",
                    "copy",
                    *audio_args,
                    "-sn",
                    *STRIP_METADATA_ARGS,
                    *mp4_faststart,
                    "-y",
                    str(temp_output),
                ]
                res = self._run_subprocess_cancellable(cmd_fb, stdout_devnull=True)

            if res.returncode != 0:
                err_detail = ""
                if hasattr(res, "stderr") and res.stderr:
                    lines = [l.strip() for l in res.stderr.splitlines() if l.strip()]
                    if lines:
                        err_detail = f" Detalle: {' '.join(lines[-2:])}"
                if errores is not None:
                    errores.append((str(video_file), f"Fallo al ejecutar ffmpeg para eliminar metadatos (código de salida: {res.returncode}).{err_detail}"))
                return False
            if temp_output.exists():
                video_file.unlink()
                ext = video_file.suffix
                self._invalidate_file_cache(video_file)
                if ext != ext.lower():
                    temp_output.rename(video_file.with_suffix(ext.lower()))
                else:
                    temp_output.rename(video_file)
                return True
            if errores is not None:
                errores.append((str(video_file), "No se pudo crear o renombrar el archivo temporal modificado."))
            return False
        except Exception as exc:
            if errores is not None:
                errores.append((str(video_file), f"Error inesperado al eliminar metadatos: {exc}"))
            return False
        finally:
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except Exception:
                    pass

    def _strip_metadata_worker(self, archivos):
        self.procesando = True
        self.cancelar_procesamiento = False

        ok = 0
        fail = 0
        total = len(archivos)
        errores = []
        self._log_message("===== INICIO ELIMINACIÓN METADATOS =====")

        fue_cancelado = False
        archivos_exitosos = []
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._log_message("Cancelado por usuario")
                fue_cancelado = True
                break
            self.msg_queue.put(("PROGRESO", i, total))
            nombre_archivo = os.path.basename(archivo)
            self._log_message(f"Eliminando metadatos {i}/{total}: {nombre_archivo}")
            self._record_activity("procesando", nombre_archivo, "Eliminar meta", "Limpiando metadatos...", item_key=f"meta:{archivo}")
            result = self._strip_file_metadata(archivo, errores)

            if self.cancelar_procesamiento:
                fue_cancelado = True
                errores = [err for err in errores if err[0] != archivo]
                break

            if result:
                archivos_exitosos.append(archivo)
                self._record_activity("exito", nombre_archivo, "Eliminar meta", "Metadatos eliminados", item_key=f"meta:{archivo}")
                ok += 1
            else:
                err_txt = next((e[1] for e in reversed(errores) if e[0] == archivo), "Error al limpiar metadatos")
                self._record_activity("error", nombre_archivo, "Eliminar meta", err_txt, item_key=f"meta:{archivo}")
                fail += 1

        self._log_message("===== FIN ELIMINACIÓN METADATOS =====")
        self.msg_queue.put(("FINALIZADO", ok, fail, errores, fue_cancelado, archivos_exitosos))
        self.procesando = False
        self.cancelar_procesamiento = False

    def strip_metadata(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        confirm = messagebox.askyesno(
            "Confirmar",
            f"Se eliminarán los metadatos en {len(archivos)} archivo(s).\nEsta acción modifica los originales.",
            icon="warning",
        )
        if not confirm:
            return

        def callback_iniciar(archivos_validos):
            self.archivos_en_proceso = list(archivos_validos)
            self._clear_log_and_progress("Preparando eliminación de metadatos...")
            self._set_running_state(True)
            threading.Thread(target=self._strip_metadata_worker, args=(archivos_validos,), daemon=True).start()
            self._poll_ui_queue()

        self.precheck_queue("eliminar_metadatos", archivos, None, callback_iniciar)

    def _strip_file_subtitles(self, video_file, errores=None):
        video_file = Path(video_file)
        info = self._ffprobe_info(video_file)
        if info is None:
            if errores is not None:
                errores.append((str(video_file), "No se pudo leer streams con ffprobe."))
            return False

        subtitle_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "subtitle" and not s.get("is_external")]
        if not subtitle_streams:
            self._log_message("  -> El archivo no contiene subtítulos internos. Saltando.")
            return True

        temp_output = video_file.parent / f"temp_{video_file.name}"
        is_mp4 = video_file.suffix.lower() in (".mp4", ".m4v")
        audio_args = ["-c:a", "copy"]

        if is_mp4 and info and "streams" in info:
            audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
            if any(s.get("codec_name", "").lower() in INCOMPATIBLE_MP4_AUDIO_CODECS for s in audio_streams):
                audio_args = ["-c:a", "aac", "-b:a", "320k"]

        cmd = [
            self.ffmpeg_path,
            "-i",
            str(video_file),
            "-map",
            "0:v?",
            "-map",
            "0:a?",
            "-c:v",
            "copy",
            *audio_args,
            "-sn",
            "-y",
            str(temp_output),
        ]
        try:
            res = self._run_subprocess_cancellable(cmd, stdout_devnull=True)
            rc = res.returncode
            if rc > 2147483647: rc -= 4294967296
            if rc != 0:
                err_detail = ""
                if hasattr(res, "stderr") and res.stderr:
                    lines = [l.strip() for l in res.stderr.splitlines() if l.strip()]
                    if lines:
                        err_detail = f" Detalle: {' '.join(lines[-2:])}"
                if errores is not None:
                    errores.append((str(video_file), f"Fallo al ejecutar ffmpeg para eliminar subtítulos (código de salida: {rc}).{err_detail}"))
                return False
            if temp_output.exists():
                video_file.unlink()
                ext = video_file.suffix
                self._invalidate_file_cache(video_file)
                if ext != ext.lower():
                    temp_output.rename(video_file.with_suffix(ext.lower()))
                else:
                    temp_output.rename(video_file)
                return True
            if errores is not None:
                errores.append((str(video_file), "No se pudo crear o renombrar el archivo temporal modificado."))
            return False
        except Exception as exc:
            if errores is not None:
                errores.append((str(video_file), f"Error inesperado al eliminar subtítulos: {exc}"))
            return False
        finally:
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except Exception:
                    pass

    def _strip_subtitles_worker(self, archivos):
        self.procesando = True
        self.cancelar_procesamiento = False

        ok = 0
        fail = 0
        total = len(archivos)
        errores = []
        self._log_message("===== INICIO ELIMINACIÓN DE SUBTÍTULOS =====")

        fue_cancelado = False
        archivos_exitosos = []
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._log_message("Cancelado por usuario")
                fue_cancelado = True
                break
            self.msg_queue.put(("PROGRESO", i, total))
            nombre_archivo = os.path.basename(archivo)
            self._log_message(f"Eliminando subs {i}/{total}: {nombre_archivo}")
            self._record_activity("procesando", nombre_archivo, "Eliminar subs", "Eliminando subtítulos...", item_key=f"subs:{archivo}")
            result = self._strip_file_subtitles(archivo, errores)

            if self.cancelar_procesamiento:
                fue_cancelado = True
                errores = [err for err in errores if err[0] != archivo]
                break

            if result:
                archivos_exitosos.append(archivo)
                self._record_activity("exito", nombre_archivo, "Eliminar subs", "Subtítulos eliminados", item_key=f"subs:{archivo}")
                ok += 1
            else:
                err_txt = next((e[1] for e in reversed(errores) if e[0] == archivo), "Error al eliminar subtítulos")
                self._record_activity("error", nombre_archivo, "Eliminar subs", err_txt, item_key=f"subs:{archivo}")
                fail += 1

        self._log_message("===== FIN ELIMINACIÓN DE SUBTÍTULOS =====")
        self.msg_queue.put(("FINALIZADO", ok, fail, errores, fue_cancelado, archivos_exitosos))
        self.procesando = False
        self.cancelar_procesamiento = False

    def strip_subtitles(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        confirm = messagebox.askyesno(
            "Confirmar",
            f"Se eliminarán todos los subtítulos de {len(archivos)} archivo(s).\nEsta acción modifica los archivos originales.",
            icon="warning",
        )
        if not confirm:
            return

        def callback_iniciar(archivos_validos):
            self.archivos_en_proceso = list(archivos_validos)
            self._clear_log_and_progress("Preparando eliminación de subtítulos...")
            self._set_running_state(True)
            threading.Thread(target=self._strip_subtitles_worker, args=(archivos_validos,), daemon=True).start()
            self._poll_ui_queue()

        self.precheck_queue("eliminar_subtitulos", archivos, None, callback_iniciar)

    def _get_file_attributes(self, filepath):
        info = self._ffprobe_info(filepath)
        attrs = {
            "resolution": "unknown",
            "codec_v": "unknown",
            "codec_a": "unknown"
        }
        if info and "streams" in info:
            video_stream = next((s for s in info["streams"] if s.get("codec_type") == "video"), {})
            attrs["codec_v"] = video_stream.get("codec_name", "unknown")
            try:
                width = int(video_stream.get("width", 0))
                height = int(video_stream.get("height", 0))
                if height >= 2160 or width >= 3840:
                    attrs["resolution"] = "2160p"
                elif height >= 1080 or width >= 1920:
                    attrs["resolution"] = "1080p"
                elif height >= 720 or width >= 1280:
                    attrs["resolution"] = "720p"
                elif height >= 480 or width >= 854:
                    attrs["resolution"] = "480p"
                elif height > 0:
                    attrs["resolution"] = f"{height}p"
            except (ValueError, TypeError):
                pass
            
            audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
            if audio_streams:
                attrs["codec_a"] = audio_streams[0].get("codec_name", "unknown")
            else:
                attrs["codec_a"] = "none"
        return attrs

    def open_renamer(self):
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video a la cola principal antes de renombrar.", parent=self.root)
            return

        # Declarar variables al inicio para uso en closures y bindings
        patron_var = tk.StringVar(value="{num} - {name}")
        inicio_var = tk.StringVar(value="1")
        digitos_var = tk.StringVar(value="2")
        buscar_var = tk.StringVar()
        reemplazar_var = tk.StringVar()
        usar_regex_var = tk.BooleanVar(value=True)

        dialog = tk.Toplevel(self.root)
        dialog.title("Renombrar Archivos")
        dialog.geometry("1260x740")
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)
        dialog.configure(bg="#F3F7FF")

        header_frame = tk.Frame(dialog, bg="#F4F8FF", highlightthickness=1, highlightbackground="#D1E2FF")
        header_frame.pack(fill=tk.X, padx=18, pady=(12, 6))
        accent_bar = tk.Frame(header_frame, width=4, bg="#2D9CDB")
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)
        text_container = tk.Frame(header_frame, bg="#F4F8FF", padx=16, pady=8)
        text_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(text_container, text="Renombrar Archivos de la Cola", font=("Segoe UI", 12, "bold"), fg="#1F2A44", bg="#F4F8FF").pack(anchor=tk.W)
        tk.Label(text_container, text="Configura un patrón de nombre para renombrar todos los archivos de la lista principal.", font=("Segoe UI", 9), fg="#5C6B8A", bg="#F4F8FF").pack(anchor=tk.W, pady=(2, 0))

        content = tk.Frame(dialog, bg="#F3F7FF", padx=18)
        content.pack(fill=tk.BOTH, expand=True)

        left_col = tk.Frame(content, bg="#F3F7FF")
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_col = tk.Frame(content, bg="#F3F7FF")
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(10, 0))

        config_frame = tk.LabelFrame(left_col, text="Configuración del Patrón", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57", padx=12, pady=10, relief=tk.GROOVE)
        config_frame.pack(fill=tk.X, pady=(4, 6))

        # Fila de Presets
        row_presets = tk.Frame(config_frame, bg="#FFFFFF")
        row_presets.pack(fill=tk.X, pady=4)
        tk.Label(row_presets, text="Ajuste predefinido:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57").pack(side=tk.LEFT, padx=(0, 6))

        PRESET_RENAME_TEMPLATES = {
            "Numeración Simple (01.mp4, 02.mp4...)": {
                "patron": "{num}", "buscar": "", "reemplazar": "", "regex": False
            },
            "Numeración + Nombre (01 - Nombre.mp4...)": {
                "patron": "{num} - {name}", "buscar": "", "reemplazar": "", "regex": False
            },
            "Extraer Capítulo (Capitulo 261 - Nombre -> 261 Nombre.mp4)": {
                "patron": "{name}", "buscar": r"Capitulo (\d+) - (.*)", "reemplazar": r"\1 \2", "regex": True
            },
            "Extraer Número de Episodio (01x03, s01e01, E09 -> 03.mp4...)": {
                "patron": "{name}", "buscar": r".*(?:s\d+e|\d+x|\b[eE]\s*|\bEp\s*|\bCapitulo\s*)(\d+).*", "reemplazar": r"\1", "regex": True
            }
        }

        try:
            custom_rename_presets = json.loads(self.config_ini.get("Options", "rename_presets", fallback="{}"))
        except Exception:
            custom_rename_presets = {}

        def obtener_todos_presets():
            todos = dict(PRESET_RENAME_TEMPLATES)
            todos.update(custom_rename_presets)
            return todos

        cb_presets = ttk.Combobox(row_presets, values=list(obtener_todos_presets().keys()), state="readonly", width=62)
        cb_presets.pack(side=tk.LEFT, padx=(0, 10))

        def on_rename_preset_selected(*_):
            sel = cb_presets.get()
            todos = obtener_todos_presets()
            if sel in todos:
                data = todos[sel]
                patron_var.set(data["patron"])
                buscar_var.set(data["buscar"])
                reemplazar_var.set(data["reemplazar"])
                usar_regex_var.set(data["regex"])

        cb_presets.bind("<<ComboboxSelected>>", on_rename_preset_selected)

        def guardar_preset_actual():
            nombre = simpledialog.askstring("Guardar Preset", "Ingresa un nombre para el preset:", parent=dialog)
            if not nombre:
                return
            nombre = nombre.strip()
            if not nombre:
                return
            if nombre in PRESET_RENAME_TEMPLATES:
                messagebox.showerror("Error", "No puedes sobrescribir los presets predefinidos del sistema.", parent=dialog)
                return
            
            try:
                curr = json.loads(self.config_ini.get("Options", "rename_presets", fallback="{}"))
            except Exception:
                curr = {}
            
            curr[nombre] = {
                "patron": patron_var.get(),
                "buscar": buscar_var.get(),
                "reemplazar": reemplazar_var.get(),
                "regex": usar_regex_var.get()
            }
            
            if "Options" not in self.config_ini:
                self.config_ini["Options"] = {}
            self.config_ini["Options"]["rename_presets"] = json.dumps(curr)
            self._save_config()
            
            nonlocal custom_rename_presets
            custom_rename_presets = curr
            
            cb_presets["values"] = list(obtener_todos_presets().keys())
            cb_presets.set(nombre)
            messagebox.showinfo("Guardado", f"Preset '{nombre}' guardado con éxito.", parent=dialog)

        def eliminar_preset_seleccionado():
            sel = cb_presets.get()
            if not sel:
                return
            if sel in PRESET_RENAME_TEMPLATES:
                messagebox.showerror("Error", "No puedes eliminar los presets predefinidos del sistema.", parent=dialog)
                return
            
            if messagebox.askyesno("Eliminar Preset", f"¿Estás seguro de que deseas eliminar el preset '{sel}'?", parent=dialog):
                try:
                    curr = json.loads(self.config_ini.get("Options", "rename_presets", fallback="{}"))
                except Exception:
                    curr = {}
                
                if sel in curr:
                    del curr[sel]
                    
                if "Options" not in self.config_ini:
                    self.config_ini["Options"] = {}
                self.config_ini["Options"]["rename_presets"] = json.dumps(curr)
                self._save_config()
                
                nonlocal custom_rename_presets
                custom_rename_presets = curr
                
                cb_presets["values"] = list(obtener_todos_presets().keys())
                cb_presets.set("")
                messagebox.showinfo("Eliminado", f"Preset '{sel}' eliminado con éxito.", parent=dialog)

        tk.Button(row_presets, text="Guardar actual", command=guardar_preset_actual, bg="#27AE60", fg="white", activebackground="#27AE60", activeforeground="white", relief=tk.FLAT, font=("Segoe UI", 9, "bold"), padx=6, cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(row_presets, text="Eliminar", command=eliminar_preset_seleccionado, bg="#EB5757", fg="white", activebackground="#EB5757", activeforeground="white", relief=tk.FLAT, font=("Segoe UI", 9, "bold"), padx=6, cursor="hand2").pack(side=tk.LEFT, padx=3)

        row_patron = tk.Frame(config_frame, bg="#FFFFFF")
        row_patron.pack(fill=tk.X, pady=4)
        tk.Label(row_patron, text="Patrón de nombre:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57").pack(side=tk.LEFT, padx=(0, 6))

        entry_patron = tk.Entry(row_patron, textvariable=patron_var, font=("Consolas", 10), bg="#F4F8FF", fg="#1F2A44", relief=tk.SOLID, bd=1)
        entry_patron.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        row_opts = tk.Frame(config_frame, bg="#FFFFFF")
        row_opts.pack(fill=tk.X, pady=4)

        tk.Label(row_opts, text="Inicio de número:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57").pack(side=tk.LEFT, padx=(0, 4))
        sp_inicio = tk.Spinbox(row_opts, from_=0, to=999999, textvariable=inicio_var, width=6, font=("Segoe UI", 9), relief=tk.SOLID, bd=1)
        sp_inicio.pack(side=tk.LEFT, padx=(0, 15))

        tk.Label(row_opts, text="Dígitos de relleno:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57").pack(side=tk.LEFT, padx=(0, 4))
        sp_digitos = tk.Spinbox(row_opts, from_=1, to=10, textvariable=digitos_var, width=4, font=("Segoe UI", 9), relief=tk.SOLID, bd=1)
        sp_digitos.pack(side=tk.LEFT, padx=(0, 15))

        row_reemplazo = tk.Frame(config_frame, bg="#FFFFFF")
        row_reemplazo.pack(fill=tk.X, pady=4)

        tk.Label(row_reemplazo, text="Buscar:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57").pack(side=tk.LEFT, padx=(0, 4))
        entry_buscar = tk.Entry(row_reemplazo, textvariable=buscar_var, font=("Consolas", 10), bg="#F4F8FF", fg="#1F2A44", relief=tk.SOLID, bd=1, width=24)
        entry_buscar.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(row_reemplazo, text="Reemplazar con:", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57").pack(side=tk.LEFT, padx=(0, 4))
        entry_reemplazar = tk.Entry(row_reemplazo, textvariable=reemplazar_var, font=("Consolas", 10), bg="#F4F8FF", fg="#1F2A44", relief=tk.SOLID, bd=1, width=24)
        entry_reemplazar.pack(side=tk.LEFT, padx=(0, 12))

        chk_regex = tk.Checkbutton(row_reemplazo, text="Usar Regex", variable=usar_regex_var, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF", font=("Segoe UI", 9))
        chk_regex.pack(side=tk.LEFT)

        row_helpers = tk.Frame(config_frame, bg="#FFFFFF")
        row_helpers.pack(fill=tk.X, pady=(6, 0))
        tk.Label(row_helpers, text="Insertar variable:", font=("Segoe UI", 8, "bold"), bg="#FFFFFF", fg="#5C6B8A").pack(side=tk.LEFT, padx=(0, 6))

        def insertar_variable(var_name):
            pos = entry_patron.index(tk.INSERT)
            entry_patron.insert(pos, var_name)
            entry_patron.focus_set()

        for var_tag in ("{name}", "{num}", "{parent}"):
            btn_h = tk.Button(
                row_helpers,
                text=var_tag,
                command=lambda v=var_tag: insertar_variable(v),
                bg="#E5ECF9",
                fg="#1F2A44",
                activebackground="#2D9CDB",
                activeforeground="white",
                relief=tk.FLAT,
                font=("Consolas", 8, "bold"),
                padx=6,
                pady=1,
                cursor="hand2"
            )
            btn_h.pack(side=tk.LEFT, padx=3)

        preview_frame = tk.LabelFrame(left_col, text="Vista Previa de Renombrado", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57", padx=12, pady=10, relief=tk.GROOVE)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 10))

        help_frame = tk.LabelFrame(right_col, text="Guía de Uso y Ejemplos", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57", padx=12, pady=10, relief=tk.GROOVE, width=360)
        help_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 10))
        help_frame.pack_propagate(False)

        help_text = (
            "Variables del Patrón:\n"
            "• {name}: Nombre original del archivo (modificado por Buscar/Reemplazar si se usa).\n"
            "• {num}: Número secuencial.\n"
            "• {parent}: Nombre de la carpeta contenedora del video.\n\n"
            "Buscar y Reemplazar:\n"
            "Útil para reestructurar nombres. Soporta Regex y grupos de captura como \\1, \\2 o $1, $2.\n\n"
            "Ejemplo de reestructuración:\n"
            "Original: \"Capitulo 261 - No estás gritando.mp4\"\n"
            "Deseado: \"261 No estás gritando.mp4\"\n"
            "1. Patrón: {name}\n"
            "2. Buscar: Capitulo (\\d+) - (.*)\n"
            "3. Reemplazar con: \\1 \\2\n"
            "4. Usar Regex: Marcado\n\n"
            "Ejemplo de numeración simple:\n"
            "Original: \"Mi_Video.mp4\"\n"
            "Deseado: \"01.mp4\"\n"
            "1. Patrón: {num}\n"
            "2. Configura Inicio (1) y Dígitos (2)."
        )

        lbl_help = tk.Label(help_frame, text=help_text, font=("Segoe UI", 9), bg="#FFFFFF", fg="#5C6B8A", justify=tk.LEFT, anchor=tk.NW, wraplength=330)
        lbl_help.pack(fill=tk.BOTH, expand=True)

        tree_container = tk.Frame(preview_frame, bg="#FFFFFF")
        tree_container.pack(fill=tk.BOTH, expand=True)

        t_act = get_theme(self.theme_var.get())
        style = ttk.Style()
        style.layout("Renamer.Treeview", [("Renamer.Treeview.treearea", {"sticky": "nswe"})])
        style.configure(
            "Renamer.Treeview",
            background=t_act["bg_surface"],
            foreground=t_act["fg_primary"],
            fieldbackground=t_act["bg_surface"],
            rowheight=26,
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 9),
        )
        style.map("Renamer.Treeview", background=[("selected", t_act["tree_sel_bg"])], foreground=[("selected", t_act["tree_sel_fg"])])
        style.configure(
            "Renamer.Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=t_act["heading_bg"],
            foreground=t_act["heading_fg"],
            relief="flat",
        )
        style.map(
            "Renamer.Treeview.Heading",
            background=[("active", t_act["bg_input"]), ("pressed", t_act["bg_input"])],
            foreground=[("active", t_act["fg_primary"]), ("pressed", t_act["fg_primary"])],
        )

        tree = ttk.Treeview(tree_container, columns=("original", "nuevo", "status"), show="headings", style="Renamer.Treeview", takefocus=False)
        tree.bind("<FocusIn>", lambda e: dialog.focus_set())
        tree.heading("original", text="Nombre Actual")
        tree.heading("nuevo", text="Nombre Nuevo Propuesto")
        tree.heading("status", text="Estado / Alerta")

        tree.column("original", width=320, anchor="w")
        tree.column("nuevo", width=340, anchor="w")
        tree.column("status", width=170, anchor="w")

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=tree.yview, style="Vertical.TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.config(yscrollcommand=scrollbar.set)

        tree.tag_configure("ok", foreground=t_act["success"])
        tree.tag_configure("conflict", foreground=t_act["warning"], font=("Segoe UI", 9, "bold"))
        tree.tag_configure("error", foreground=t_act["danger"], font=("Segoe UI", 9, "bold"))
        tree.tag_configure("no_change", foreground=t_act["fg_muted"])

        item_to_path = {}

        def _es_nombre_valido(nombre):
            if not nombre.strip():
                return False
            invalidos = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
            return not any(c in nombre for c in invalidos)

        def actualizar_preview(*_):
            for item in tree.get_children():
                tree.delete(item)
            item_to_path.clear()

            patron = patron_var.get()
            try:
                inicio = int(inicio_var.get())
            except ValueError:
                inicio = 1
            try:
                digitos = int(digitos_var.get())
            except ValueError:
                digitos = 2

            from collections import Counter
            new_paths = []
            parsed_results = []

            for idx, filepath in enumerate(archivos):
                num_val = inicio + idx
                num_str = f"{num_val:0{digitos}d}"

                parent_dir = os.path.dirname(filepath)
                name_with_ext = os.path.basename(filepath)
                stem, ext = os.path.splitext(name_with_ext)
                parent_name = os.path.basename(parent_dir)

                # Apply Buscar y Reemplazar on original stem
                buscar = buscar_var.get()
                reemplazar = reemplazar_var.get()
                if buscar:
                    if usar_regex_var.get():
                        try:
                            import re
                            py_reemplazar = reemplazar
                            py_reemplazar = re.sub(r'\$(\d+)', lambda m: f'\\g<{m.group(1)}>', py_reemplazar)
                            py_reemplazar = re.sub(r'\\(\d+)', lambda m: f'\\g<{m.group(1)}>', py_reemplazar)
                            stem = re.sub(buscar, py_reemplazar, stem, flags=re.IGNORECASE)
                        except Exception:
                            # In case of invalid regex, keep stem unchanged
                            pass
                    else:
                        stem = stem.replace(buscar, reemplazar)

                resolution = "unknown"
                codec_v = "unknown"
                codec_a = "unknown"

                if any(tag in patron for tag in ("{resolution}", "{codec_v}", "{codec_a}")):
                    attrs = self._get_file_attributes(filepath)
                    resolution = attrs["resolution"]
                    codec_v = attrs["codec_v"]
                    codec_a = attrs["codec_a"]

                resolved = patron
                resolved = resolved.replace("{name}", stem)
                resolved = resolved.replace("{num}", num_str)
                resolved = resolved.replace("{parent}", parent_name)
                resolved = resolved.replace("{resolution}", resolution)
                resolved = resolved.replace("{codec_v}", codec_v)
                resolved = resolved.replace("{codec_a}", codec_a)

                new_name = resolved + ext
                new_path = os.path.join(parent_dir, new_name)
                new_paths.append(os.path.normcase(os.path.normpath(new_path)))
                parsed_results.append((filepath, new_name, new_path))

            path_counts = Counter(new_paths)

            for filepath, new_name, new_path in parsed_results:
                orig_norm = os.path.normcase(os.path.normpath(filepath))
                dest_norm = os.path.normcase(os.path.normpath(new_path))

                if not _es_nombre_valido(new_name):
                    status = "Error: Caracteres inválidos"
                    tag = "error"
                elif path_counts[dest_norm] > 1:
                    status = "Conflicto: Duplicado en cola"
                    tag = "conflict"
                elif os.path.exists(new_path) and dest_norm != orig_norm:
                    status = "Conflicto: Ya existe en disco"
                    tag = "conflict"
                elif dest_norm == orig_norm:
                    status = "Sin cambios"
                    tag = "no_change"
                else:
                    status = "Listo"
                    tag = "ok"

                item_id = tree.insert("", tk.END, values=(os.path.basename(filepath), new_name, status), tags=(tag,))
                item_to_path[item_id] = filepath

        patron_var.trace_add("write", actualizar_preview)
        inicio_var.trace_add("write", actualizar_preview)
        digitos_var.trace_add("write", actualizar_preview)
        buscar_var.trace_add("write", actualizar_preview)
        reemplazar_var.trace_add("write", actualizar_preview)
        usar_regex_var.trace_add("write", actualizar_preview)
        
        actualizar_preview()

        btm = tk.Frame(dialog, bg="#F3F7FF")
        btm.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 16))

        btn_container = tk.Frame(btm, bg="#F3F7FF")
        btn_container.pack(anchor=tk.CENTER)

        btn_ok = tk.Button(btn_container, text="Aplicar Renombrado", command=lambda: self._execute_renaming(dialog, archivos, tree, item_to_path), bg="#27AE60", fg="white", width=22, relief=tk.FLAT, font=("Segoe UI", 10, "bold"), cursor="hand2")
        btn_ok.pack(side=tk.LEFT, padx=10)

        btn_cancel = tk.Button(btn_container, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=12, relief=tk.FLAT, font=("Segoe UI", 10, "bold"), cursor="hand2")
        btn_cancel.pack(side=tk.LEFT, padx=10)

    def _execute_renaming(self, dialog, archivos, tree, item_to_path=None):
        if not archivos:
            messagebox.showwarning("Sin archivos", "No hay archivos en la cola para renombrar.", parent=dialog)
            return

        has_errors = False
        has_conflicts = False
        items = tree.get_children()

        for item_id in items:
            vals = tree.item(item_id, "values")
            status = vals[2]
            if "Error" in status:
                has_errors = True
            elif "Conflicto" in status:
                has_conflicts = True

        if has_errors:
            messagebox.showerror("Error de Validación", "Por favor, corrija los errores de caracteres inválidos antes de aplicar el renombrado.", parent=dialog)
            return

        if has_conflicts:
            confirm = messagebox.askyesno(
                "Confirmar Conflictos",
                "Hay conflictos detectados (nombres duplicados o archivos existentes en disco).\n"
                "¿Desea continuar de todos modos? Algunos archivos podrían no renombrarse o sobrescribirse.",
                parent=dialog,
                icon="warning"
            )
            if not confirm:
                return
        else:
            confirm = messagebox.askyesno(
                "Confirmar Renombrado",
                f"¿Desea proceder a renombrar los {len(archivos)} archivos de la cola?",
                parent=dialog
            )
            if not confirm:
                return

        self._clear_log_and_progress("Renombrando archivos...")
        self._log_message("===== INICIO RENOMBRADO DE ARCHIVOS =====")
        ok_count = 0
        fail_count = 0
        mapping_renombres = {}

        for item_id in items:
            _, proposed_name, status = tree.item(item_id, "values")
            original_path = item_to_path.get(item_id) if item_to_path else _

            if status == "Sin cambios":
                mapping_renombres[original_path] = original_path
                continue

            parent_dir = os.path.dirname(original_path)
            new_path = os.path.join(parent_dir, proposed_name)

            if os.path.normcase(os.path.normpath(original_path)) == os.path.normcase(os.path.normpath(new_path)):
                mapping_renombres[original_path] = original_path
                continue

            try:
                os.rename(original_path, new_path)
                self._invalidate_file_cache(original_path)
                self._log_message(f"Renombrado con éxito:\n  De: {original_path}\n  A: {new_path}")
                self._record_activity("exito", os.path.basename(new_path), "Renombrado", f"Antes: {os.path.basename(original_path)}")
                mapping_renombres[original_path] = new_path
                ok_count += 1
            except Exception as exc:
                self._log_message(f"Error al renombrar {os.path.basename(original_path)}: {exc}")
                self._record_activity("error", os.path.basename(original_path), "Renombrado", str(exc))
                mapping_renombres[original_path] = original_path
                fail_count += 1

        self.progress["value"] = 100
        self.progress_label.config(text=f"Renombrado completado | Éxitos: {ok_count} | Fallos: {fail_count}")

        all_items = list(self.lista.get(0, tk.END))
        self.lista.delete(0, tk.END)
        for path in all_items:
            new_val = mapping_renombres.get(path, path)
            self.lista.insert(tk.END, os.path.normpath(new_val))
        self._update_queue_counters()

        self._log_message("===== FIN RENOMBRADO DE ARCHIVOS =====")
        self._log_message(f"Renombrados con éxito: {ok_count} | Errores: {fail_count}")

        dialog.destroy()
        messagebox.showinfo("Renombrado Finalizado", f"Se han renombrado {ok_count} archivos correctamente.\nErrores: {fail_count}")

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

    def _resolve_subfolder_pattern(self, filepath, info, label, audio_indices, sub_indices):
        return _resolver_patron_subcarpeta_helper(
            self.var_nombre_subcarpeta.get(),
            filepath,
            info,
            label,
            audio_indices,
            sub_indices,
        )

    def _open_path_builder(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Constructor de Ruta de Salida")
        dialog.geometry("750x660")
        dialog.minsize(720, 620)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)
        dialog.configure(bg="#F3F7FF")

        tk.Label(dialog, text="Constructor de Ruta de Salida", font=("Segoe UI", 12, "bold"), bg="#F3F7FF", fg="#1F2A44").pack(pady=(12, 6))
        tk.Label(dialog, text="Haz clic en las banderas para agregarlas al patrón de subcarpeta:", font=("Segoe UI", 9), bg="#F3F7FF", fg="#5C6B8A").pack(pady=(0, 10))

        patron_var = tk.StringVar(value=self.var_nombre_subcarpeta.get())
        entry = tk.Entry(dialog, textvariable=patron_var, font=("Consolas", 11), bg="#FFFFFF", fg="#1F2A44", relief=tk.SOLID, bd=1)
        entry.pack(fill=tk.X, padx=20, pady=8)
        entry.focus_set()

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
                self._save_config()
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
                self._save_config()
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
        flags_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(4, 10))
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

        btm.pack(side=tk.BOTTOM, pady=(5, 12))
        preview_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=10)

        tk.Label(preview_frame, text="Vista previa de ruta resuelta:", font=("Segoe UI", 9, "bold"), bg="#E5ECF9", fg="#2B3A57").pack(anchor=tk.W)
        preview_lbl = tk.Label(preview_frame, text="", font=("Consolas", 9), bg="#E5ECF9", fg="#1F2A44", wraplength=680, justify=tk.LEFT)
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
            resolved = self._resolve_subfolder_pattern(f"C:/ruta/de/ejemplo/{video_name}.mp4", info, "ESP_subENG", audio_indices, sub_indices)
            self.var_nombre_subcarpeta.set(old_val)

            base_dir = self.salida_var.get().strip() or obtener_directorio_videos_defecto()
            sub_dir = f"{resolved}/" if resolved else ""
            preview_lbl.config(text=f"{base_dir}/{sub_dir}{video_name}.mp4")

        patron_var.trace_add("write", actualizar_preview)
        actualizar_preview()

        def aceptar():
            self.var_nombre_subcarpeta.set(patron_var.get())
            dialog.destroy()

        tk.Button(btm, text="Guardar", command=aceptar, bg="#27AE60", fg="white", width=12, relief=tk.FLAT, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=6)
        tk.Button(btm, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=12, relief=tk.FLAT, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=6)

    def cancel_processing(self):
        if not self.procesando:
            messagebox.showinfo("Sin proceso", "No hay procesamiento activo")
            return
        if messagebox.askyesno("Cancelar todo", "Deseas cancelar el procesamiento actual y detener toda la cola de videos?"):
            self.cancelar_procesamiento = True
            self._clear_subgroups()
            if self.proceso_actual:
                try:
                    self.proceso_actual.terminate()
                except Exception:
                    pass
            self.btn_cancelar.config(state=tk.DISABLED)
            self._log_message("Solicitud de cancelacion enviada...")

    def _run_subprocess_cancellable(self, cmd, stdout_devnull=False):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        stderr_lines = []
        def _read_stderr(pipe):
            try:
                for line in iter(pipe.readline, ''):
                    if line:
                        stderr_lines.append(line)
            except Exception:
                pass
            finally:
                pipe.close()

        self.proceso_actual = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo
        )

        stderr_thread = threading.Thread(target=_read_stderr, args=(self.proceso_actual.stderr,), daemon=True)
        stderr_thread.start()

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
                stderr_thread.join(timeout=0.5)
                return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="".join(stderr_lines))

            ret = self.proceso_actual.poll()
            if ret is not None:
                stderr_thread.join(timeout=0.5)
                if ret > 0x7FFFFFFF:
                    ret = ret - 0x100000000
                return subprocess.CompletedProcess(cmd, returncode=ret, stdout="", stderr="".join(stderr_lines))

            time.sleep(0.1)

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
            messagebox.showinfo("Actualizado", f"FFmpeg y FFProbe actualizados\n\n{archivo}")
        else:
            messagebox.showinfo("Actualizado", f"FFmpeg actualizado\n\n{archivo}\n\nSelecciona FFProbe manualmente si hace falta")
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
            messagebox.showinfo("Actualizado", f"FFProbe actualizado\n\n{archivo}")

    def show_ffmpeg_info(self):
        messagebox.showinfo(
            "Rutas configuradas",
            f"FFmpeg:\n{self.ffmpeg_path}\n\nFFProbe:\n{self.ffprobe_path}\n\nConfiguracion VW:\n{CONFIG_DIR}\n\nCarpeta Tools (Portatil):\n{os.path.join(obtener_ruta_base_app(), 'tools')}",
        )

    def change_preset(self):
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
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)

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

    def show_about(self):
        import webbrowser

        dialog = tk.Toplevel(self.root)
        dialog.title("Acerca de Video Workstation (VW)")
        dialog.geometry("560x350")
        dialog.resizable(False, False)
        dialog.configure(bg="#F3F7FF")
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        header_card = tk.Frame(dialog, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5ECF9", bd=0)
        header_card.pack(fill=tk.X, padx=18, pady=(14, 8))

        text_container = tk.Frame(header_card, bg="#FFFFFF")
        text_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=14, pady=10)

        t_act = get_theme(self.theme_var.get())
        tk.Label(
            text_container,
            text="VW",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg=t_act["accent"],
            padx=8,
            pady=2,
        ).pack(side=tk.LEFT)

        tk.Label(
            text_container,
            text="  Acerca de Video Workstation",
            font=("Segoe UI", 10, "bold"),
            fg="#1F2A44",
            bg="#FFFFFF"
        ).pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(
            header_card,
            text=f"v{VERSION}",
            font=("Segoe UI", 9, "bold"),
            bg="#FFFFFF",
            fg="#2D9CDB"
        ).pack(side=tk.RIGHT, padx=14, pady=10)

        content_card = tk.Frame(dialog, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5ECF9", bd=0)
        content_card.pack(fill=tk.BOTH, expand=True, padx=18, pady=(4, 10))

        content = tk.Frame(content_card, bg="#FFFFFF", padx=16, pady=12)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            content,
            text="Video Workstation",
            font=("Segoe UI", 12, "bold"),
            bg="#FFFFFF",
            fg="#1F2A44"
        ).pack(anchor=tk.W)

        desc = (
            "Video Workstation (VW) es una estación de trabajo para la optimización de flujos de trabajo de vídeo. "
            "Automatiza la multiplexación de audio/subtítulos (remux), la codificación acelerada por hardware "
            "(NVIDIA NVENC, Intel QSV, AMD AMF) con incrustado de subtítulos (hardsub), el renombrado masivo "
            "por lotes con expresiones regulares, la limpieza de metadatos in-place y la organización en rutas dinámicas."
        )
        tk.Label(
            content,
            text=desc,
            font=("Segoe UI", 9),
            bg="#FFFFFF",
            fg="#5C6B8A",
            justify=tk.LEFT,
            wraplength=460
        ).pack(anchor=tk.W, pady=(6, 10))

        tk.Frame(content, height=1, bg="#E5ECF9").pack(fill=tk.X, pady=(0, 10))

        info_frame = tk.Frame(content, bg="#FFFFFF")
        info_frame.pack(fill=tk.X)
        info_frame.columnconfigure(1, weight=1)

        tk.Label(
            info_frame,
            text="Desarrolladores:",
            font=("Segoe UI", 9, "bold"),
            bg="#FFFFFF",
            fg="#2B3A57"
        ).grid(row=0, column=0, sticky=tk.NW, pady=3)

        devs_subframe = tk.Frame(info_frame, bg="#FFFFFF")
        devs_subframe.grid(row=0, column=1, sticky=tk.W, padx=12, pady=3)

        dev1_lbl = tk.Label(
            devs_subframe,
            text="• Gabriel Giraldo Herrera (github.com/TheHexenjagd)",
            font=("Segoe UI", 9, "underline"),
            bg="#FFFFFF",
            fg="#2D9CDB",
            cursor="hand2"
        )
        dev1_lbl.pack(anchor=tk.W, pady=1)
        dev1_lbl.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/TheHexenjagd"))

        dev2_lbl = tk.Label(
            devs_subframe,
            text="• Jorge Iván Nieto Triviño (github.com/Gatozo)",
            font=("Segoe UI", 9, "underline"),
            bg="#FFFFFF",
            fg="#2D9CDB",
            cursor="hand2"
        )
        dev2_lbl.pack(anchor=tk.W, pady=1)
        dev2_lbl.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/Gatozo"))

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
        btn_close.pack(side=tk.BOTTOM, pady=(0, 12))

    def _show_error_summary(self, errores):
        dialog = tk.Toplevel(self.root)
        dialog.title("Resumen de Errores - VW")
        dialog.geometry("740x500")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)
        dialog.configure(bg="#F3F7FF")

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        header = tk.Frame(dialog, bg="#1A2536", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Resumen de Errores de Procesamiento",
            font=("Segoe UI", 14, "bold"),
            bg="#1A2536",
            fg="#FFFFFF"
        ).pack(anchor=tk.W, padx=20, pady=(10, 2))

        tk.Label(
            header,
            text="Los siguientes problemas ocurrieron al procesar los archivos de la cola:",
            font=("Segoe UI", 9),
            bg="#1A2536",
            fg="#B0C4DE"
        ).pack(anchor=tk.W, padx=20)

        body = tk.Frame(dialog, bg="#F3F7FF", padx=20, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        text_frame = tk.Frame(body, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5ECF9")
        text_frame.pack(fill=tk.BOTH, expand=True)

        log_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            bg="#FFFFFF",
            fg="#1F2A44",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame, command=log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.config(yscrollcommand=scrollbar.set)

        log_text.tag_config("file_title", font=("Segoe UI", 10, "bold"), spacing1=8, spacing3=2)
        log_text.tag_config("error_lbl", font=("Segoe UI", 9, "bold"), foreground="#EB5757")
        log_text.tag_config("detail", font=("Segoe UI", 9), foreground="#4F4F4F", lmargin1=25, lmargin2=25, spacing3=4)

        for archivo, err_desc in errores:
            basename = os.path.basename(archivo) if archivo != "General" else "General"
            log_text.insert(tk.END, f"Archivo: {basename}\n", "file_title")
            log_text.insert(tk.END, "  [ERROR] ", "error_lbl")
            log_text.insert(tk.END, f"{err_desc}\n", "detail")

        log_text.config(state=tk.DISABLED)

        btm = tk.Frame(dialog, bg="#F3F7FF")
        btm.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(5, 15))

        btn_cerrar = tk.Button(
            btm,
            text="Cerrar",
            command=dialog.destroy,
            bg="#2D9CDB",
            fg="white",
            activebackground="#2185C5",
            activeforeground="white",
            relief=tk.FLAT,
            padx=20,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_cerrar.pack(side=tk.RIGHT)

    def exit_application(self):
        if self.procesando and not messagebox.askyesno("Proceso activo", "Hay un proceso en curso. Salir de todos modos?"):
            return

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
