import configparser
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

VERSION = "1.0.0"

class RoundedButton(tk.Canvas):
    def __init__(self, master, text="", command=None, bg="#2D9CDB", fg="white",
                 activebackground=None, activeforeground="white", relief=None,
                 width=None, height=None, font=("Segoe UI", 9, "bold"),
                 padx=10, pady=4, state=tk.NORMAL, cursor="hand2", **kwargs):
        
        self.master = master
        self.text = text
        self.command = command
        self.bg_color = bg
        self.fg_color = fg
        self.active_bg = activebackground if activebackground else self._adjust_brightness(bg, -15)
        self.active_fg = activeforeground
        self.font = font
        self.state = state
        self.padx = padx
        self.pady = pady
        self.fixed_width = width is not None
        
        # Measure text width/height
        f_obj = tkfont.Font(font=self.font)
        text_w = f_obj.measure(text)
        text_h = f_obj.metrics("linespace")
        
        # Determine height
        if height is not None:
            self.height = height
        else:
            self.height = text_h + 2 * pady + 6
            
        # Determine width
        if width is not None:
            if width <= 40:  # character count
                self.width = max(text_w + 2 * padx, width * 8)
            else:  # pixel count
                self.width = width
        else:
            self.width = text_w + 2 * padx + 12
            
        # Parent background for canvas edges (transparency simulation)
        parent_bg = "#F3F7FF"  # default app background
        if master:
            try:
                bg_val = master.cget("bg")
                if bg_val:
                    parent_bg = bg_val
            except Exception:
                try:
                    bg_val = master.cget("background")
                    if bg_val:
                        parent_bg = bg_val
                except Exception:
                    try:
                        style_name = master.cget("style")
                        if style_name:
                            style = ttk.Style()
                            bg_val = style.lookup(style_name, "background")
                            if bg_val:
                                parent_bg = bg_val
                    except Exception:
                        pass
        
        # Pop standard button options that Canvas config doesn't accept
        kwargs.pop("activebackground", None)
        kwargs.pop("activeforeground", None)
        kwargs.pop("relief", None)
        kwargs.pop("compound", None)
        kwargs.pop("overrelief", None)
        kwargs.pop("repeatdelay", None)
        kwargs.pop("repeatinterval", None)
        kwargs.pop("takefocus", None)
        kwargs.pop("text", None)
        kwargs.pop("command", None)
        
        super().__init__(master, bg=parent_bg, bd=0, highlightthickness=0,
                         width=self.width, height=self.height, cursor=cursor if state == tk.NORMAL else "", **kwargs)
        
        self.rect_id = None
        self.text_id = None
        self.pressed = False
        
        self.draw_button()
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        
    def _adjust_brightness(self, hex_color, percent):
        try:
            if not hex_color.startswith("#") or len(hex_color) != 7:
                return hex_color
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            
            r = max(0, min(255, r + percent))
            g = max(0, min(255, g + percent))
            b = max(0, min(255, b + percent))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def get_rounded_rect_points(self, x1, y1, x2, y2, r):
        points = []
        steps = 8
        # Top-right
        for i in range(steps + 1):
            theta = -math.pi/2 + (math.pi/2) * (i / steps)
            points.append(x2 - r + r * math.cos(theta))
            points.append(y1 + r + r * math.sin(theta))
        # Bottom-right
        for i in range(steps + 1):
            theta = 0 + (math.pi/2) * (i / steps)
            points.append(x2 - r + r * math.cos(theta))
            points.append(y2 - r + r * math.sin(theta))
        # Bottom-left
        for i in range(steps + 1):
            theta = math.pi/2 + (math.pi/2) * (i / steps)
            points.append(x1 + r + r * math.cos(theta))
            points.append(y2 - r + r * math.sin(theta))
        # Top-left
        for i in range(steps + 1):
            theta = math.pi + (math.pi/2) * (i / steps)
            points.append(x1 + r + r * math.cos(theta))
            points.append(y1 + r + r * math.sin(theta))
        return points

    def draw_button(self, fill_color=None):
        self.delete("all")
        if fill_color is None:
            if self.state == tk.DISABLED:
                fill_color = "#E0E0E0"
            else:
                fill_color = self.bg_color
                
        text_color = self.fg_color
        if self.state == tk.DISABLED:
            text_color = "#A0A0A0"
            self.config(cursor="")
        else:
            self.config(cursor="hand2")
            
        r = 6  # corner radius
        r = min(r, self.width // 2, self.height // 2)
        
        points = self.get_rounded_rect_points(0, 0, self.width, self.height, r)
        self.rect_id = self.create_polygon(points, fill=fill_color, outline="", smooth=False)
        self.text_id = self.create_text(self.width / 2, self.height / 2, text=self.text, fill=text_color, font=self.font, justify=tk.CENTER)

    def config(self, cnf=None, **kw):
        if cnf is not None:
            kw.update(cnf)
        
        redraw = False
        if "state" in kw:
            self.state = kw.pop("state")
            redraw = True
        if "text" in kw:
            self.text = kw.pop("text")
            if not self.fixed_width:
                f_obj = tkfont.Font(font=self.font)
                self.width = f_obj.measure(self.text) + 2 * self.padx + 12
                super().config(width=self.width)
            redraw = True
        if "command" in kw:
            self.command = kw.pop("command")
        if "bg" in kw or "background" in kw:
            self.bg_color = kw.pop("bg") if "bg" in kw else kw.pop("background")
            self.active_bg = self._adjust_brightness(self.bg_color, -15)
            redraw = True
        if "fg" in kw or "foreground" in kw:
            self.fg_color = kw.pop("fg") if "fg" in kw else kw.pop("foreground")
            redraw = True
            
        kw.pop("activebackground", None)
        kw.pop("activeforeground", None)
        kw.pop("relief", None)
        kw.pop("compound", None)
        
        if kw:
            super().config(**kw)
            
        if redraw:
            self.draw_button()
            
    def configure(self, cnf=None, **kw):
        self.config(cnf, **kw)
        
    def cget(self, option):
        if option == "state":
            return self.state
        elif option in ("bg", "background"):
            return self.bg_color
        elif option in ("fg", "foreground"):
            return self.fg_color
        elif option == "text":
            return self.text
        return super().cget(option)
        
    def __getitem__(self, item):
        return self.cget(item)

    def on_enter(self, event):
        if self.state == tk.NORMAL:
            self.draw_button(self.active_bg)

    def on_leave(self, event):
        if self.state == tk.NORMAL:
            self.draw_button(self.bg_color)
            self.pressed = False

    def on_press(self, event):
        if self.state == tk.NORMAL:
            self.pressed = True
            press_bg = self._adjust_brightness(self.bg_color, -30)
            self.draw_button(press_bg)

    def on_release(self, event):
        if self.state == tk.NORMAL and self.pressed:
            self.pressed = False
            self.draw_button(self.active_bg)
            if self.command:
                self.command()

tk.Button = RoundedButton


_appdata_env = os.getenv("APPDATA")
if _appdata_env:
    CONFIG_DIR = os.path.join(_appdata_env, "VideoWorkstation")
else:
    _xdg_cfg = os.getenv("XDG_CONFIG_HOME", os.path.join(str(Path.home()), ".config"))
    CONFIG_DIR = os.path.join(_xdg_cfg, "VideoWorkstation")

os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "vw_config.ini")
QUEUE_FILE = os.path.join(CONFIG_DIR, "vw_queue.ini")

TOOLS_DIR = os.path.join(CONFIG_DIR, "tools")
os.makedirs(TOOLS_DIR, exist_ok=True)

def obtener_directorio_videos_defecto():
    """
    Retorna la ruta predeterminada de la carpeta de videos del usuario
    de forma multiplataforma (Windows, Linux, macOS).
    """
    # 1. Windows: SHGetFolderPathW con CSIDL_MYVIDEO (0x000e)
    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x000e, None, 0, buf) == 0 and buf.value:
                os.makedirs(buf.value, exist_ok=True)
                return os.path.abspath(buf.value)
        except Exception:
            pass
        path_win = os.path.join(str(Path.home()), "Videos")
        try:
            os.makedirs(path_win, exist_ok=True)
        except Exception:
            pass
        return os.path.abspath(path_win)

    # 2. macOS (Darwin): estándar ~/Movies o ~/Videos
    elif sys.platform == "darwin":
        movies_dir = os.path.join(str(Path.home()), "Movies")
        if os.path.isdir(movies_dir):
            return os.path.abspath(movies_dir)
        videos_dir = os.path.join(str(Path.home()), "Videos")
        if os.path.isdir(videos_dir):
            return os.path.abspath(videos_dir)
        try:
            os.makedirs(movies_dir, exist_ok=True)
        except Exception:
            pass
        return os.path.abspath(movies_dir)

    # 3. Linux / Unix: consultar XDG User Dirs o ~/Videos
    else:
        xdg_videos = os.getenv("XDG_VIDEOS_DIR")
        if xdg_videos and os.path.isdir(xdg_videos):
            return os.path.abspath(xdg_videos)

        xdg_config = os.getenv("XDG_CONFIG_HOME", os.path.join(str(Path.home()), ".config"))
        user_dirs_file = os.path.join(xdg_config, "user-dirs.dirs")
        if os.path.isfile(user_dirs_file):
            try:
                with open(user_dirs_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("XDG_VIDEOS_DIR="):
                            val = line.split("=", 1)[1].strip('"\'')
                            val = val.replace("$HOME", str(Path.home()))
                            if os.path.isdir(val):
                                return os.path.abspath(val)
            except Exception:
                pass

        videos_dir = os.path.join(str(Path.home()), "Videos")
        try:
            os.makedirs(videos_dir, exist_ok=True)
        except Exception:
            pass
        return os.path.abspath(videos_dir)

def obtener_ruta_base_app():
    """Retorna el directorio base donde reside el ejecutable empaquetado o el script en ejecucion."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def resolver_ruta_binario(nombre_binario):
    """
    Resolucion inteligente de binarios (Modo Portatil e Independiente):
    1. Directorio local ./tools/<nombre> junto a VW (Modo Portatil 100% autonomo)
    2. Directorio dedicado de la aplicacion: %APPDATA%/VideoWorkstation/tools/<nombre>
    3. PATH del sistema operativo (shutil.which)
    4. Fallback predeterminado a %APPDATA%/VideoWorkstation/tools/<nombre>
    """
    app_base = obtener_ruta_base_app()

    # 1. Modo Portatil: ./tools/ junto a VW
    ruta_portable = os.path.join(app_base, "tools", nombre_binario)
    if os.path.isfile(ruta_portable):
        return os.path.abspath(ruta_portable)

    # 2. Directorio dedicado en AppData de VW
    ruta_vw_tools = os.path.join(TOOLS_DIR, nombre_binario)
    if os.path.isfile(ruta_vw_tools):
        return ruta_vw_tools

    # 3. PATH del sistema operativo
    nombre_base = os.path.splitext(nombre_binario)[0]
    en_path = shutil.which(nombre_binario) or shutil.which(nombre_base)
    if en_path and os.path.isfile(en_path):
        return os.path.abspath(en_path)

    # 4. Fallback por defecto
    return ruta_vw_tools

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".ts", ".m4v")
BITMAP_SUB_CODECS = {
    "hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub",
    "dvb_teletext", "eia_608", "cea_708", "teletext", "arib_caption",
    "subviewer", "pjs", "vplayer"
}
INCOMPATIBLE_MP4_AUDIO_CODECS = {
    "dca", "dts", "flac", "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_s8",
    "pcm_u8", "pcm_bluray", "pcm_dvd", "pcm_alaw", "pcm_mulaw", "truehd",
    "mlp", "vorbis", "opus"
}

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
        "ffmpeg": resolver_ruta_binario("ffmpeg.exe"),
        "ffprobe": resolver_ruta_binario("ffprobe.exe"),
        "output_dir": obtener_directorio_videos_defecto(),
    },
    "Options": {
        "buscar_recursivo": "True",
        "crear_subcarpeta": "False",
        "nombre_subcarpeta": "",
        "usar_nvidia": "True",
        "gpu_acel": "nvidia",
        "decod_hw": "Software",
        "preset": "medium",
        "sufijo_idiomas": "True",
        "eliminar_metadatos": "False",
        "preservar_color": "True",
    },
}

def obtener_identificador_pista(stream):
    tags = stream.get("tags") or {}
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
        tags = stream.get("tags") or {}
        if (
            tags.get("language", "und") == lang_buscado
            and tags.get("title", "") == title_buscado
            and stream.get("codec_name", "unknown") == codec_buscado
        ):
            return stream["index"]

    for stream in streams:
        if stream.get("codec_type") != codec_type:
            continue
        tags = stream.get("tags") or {}
        if tags.get("language", "und") == lang_buscado and tags.get("title", "") == title_buscado:
            return stream["index"]

    for stream in streams:
        if stream.get("codec_type") != codec_type:
            continue
        tags = stream.get("tags") or {}
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

class VWSuite:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Video Workstation (VW)")
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
        if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
            self.ffmpeg_path = resolver_ruta_binario("ffmpeg.exe")
        if not self.ffprobe_path or not os.path.exists(self.ffprobe_path):
            self.ffprobe_path = resolver_ruta_binario("ffprobe.exe")

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

        self._crear_estilos()
        self._crear_menu()
        self._crear_ui()
        self._verificar_ffmpeg_inicio()
        self._iniciar_deteccion_gpus()

        self.root.protocol("WM_DELETE_WINDOW", self.salir_aplicacion)

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
                if config.has_section("Queue"):
                    config.remove_section("Queue")
                    self._guardar_configuracion(config)
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
            self.config_ini["Options"]["crear_subcarpeta"] = str(self.var_subcarpeta.get())
            self.config_ini["Options"]["nombre_subcarpeta"] = self.var_nombre_subcarpeta.get()
            self.config_ini["Options"]["gpu_acel"] = self.gpu_acel_var.get()
            self.config_ini["Options"]["decod_hw"] = self.decod_hw_var.get()
            self.config_ini["Options"]["usar_nvidia"] = str(self.gpu_acel_var.get() == "nvidia")
            self.config_ini["Options"]["preset"] = self.preset_var.get()
            self.config_ini["Options"]["sufijo_idiomas"] = str(self.var_sufijo_idiomas.get())
            self.config_ini["Options"]["eliminar_metadatos"] = str(self.var_eliminar_metadatos.get())
            self.config_ini["Options"]["preservar_color"] = str(self.var_preservar_color.get())

            self._guardar_configuracion()
        except Exception as exc:
            print(f"Error actualizando configuracion: {exc}")

    def _crear_estilos(self):
        self.root.configure(bg="#F3F7FF")
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("VW.TFrame", background="#F3F7FF")
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
        self.var_subcarpeta = tk.BooleanVar(value=self.config_ini.getboolean("Options", "crear_subcarpeta", fallback=False))
        self.var_nombre_subcarpeta = tk.StringVar(value=self.config_ini.get("Options", "nombre_subcarpeta", fallback=""))
        self.gpu_acel_var = tk.StringVar(value=self._obtener_gpu_inicial())
        self.decod_hw_var = tk.StringVar(value=self.config_ini.get("Options", "decod_hw", fallback="Software"))
        self.preset_var = tk.StringVar(value=self.config_ini.get("Options", "preset", fallback="medium"))
        salida_default = self.config_ini.get("Paths", "output_dir", fallback="").strip()
        if not salida_default:
            salida_default = obtener_directorio_videos_defecto()
            if "Paths" not in self.config_ini:
                self.config_ini["Paths"] = {}
            self.config_ini["Paths"]["output_dir"] = salida_default
            self._guardar_configuracion()
        self.salida_var = tk.StringVar(value=salida_default)
        self.var_sufijo_idiomas = tk.BooleanVar(value=self.config_ini.getboolean("Options", "sufijo_idiomas", fallback=True))
        self.var_eliminar_metadatos = tk.BooleanVar(
            value=self.config_ini.getboolean("Options", "eliminar_metadatos",
                  fallback=self.config_ini.getboolean("Options", "limpiar_metadatos", fallback=False))
        )
        self.var_preservar_color = tk.BooleanVar(
            value=self.config_ini.getboolean("Options", "preservar_color", fallback=True)
        )

        for var in [
            self.var_recursivo,
            self.var_subcarpeta,
            self.var_nombre_subcarpeta,
            self.gpu_acel_var,
            self.decod_hw_var,
            self.preset_var,
            self.salida_var,
            self.var_sufijo_idiomas,
            self.var_eliminar_metadatos,
            self.var_preservar_color,
        ]:
            var.trace_add("write", self._actualizar_configuracion)

        main = ttk.Frame(self.root, style="VW.TFrame")
        main.pack(fill=tk.BOTH, expand=True)

        hero_card = tk.Frame(main, bg="#F4F8FF", highlightthickness=1, highlightbackground="#D1E2FF", bd=0)
        hero_card.pack(fill=tk.X, padx=18, pady=(8, 4))

        accent_bar = tk.Frame(hero_card, width=4, bg="#2D9CDB")
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        text_container = tk.Frame(hero_card, bg="#F4F8FF")
        text_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=16, pady=6)

        tk.Label(
            text_container,
            text="VW",
            font=("Segoe UI", 12, "bold"),
            fg="#1F2A44",
            bg="#F4F8FF"
        ).pack(side=tk.LEFT)

        tk.Label(
            text_container,
            text="  |  Video Workstation - Procesamiento de vídeo, multiplexación y hardsub",
            font=("Segoe UI", 9),
            fg="#5C6B8A",
            bg="#F4F8FF"
        ).pack(side=tk.LEFT, padx=(4, 0))

        top = ttk.Frame(main, style="VW.TFrame")
        top.pack(fill=tk.BOTH, expand=False, padx=18, pady=6)

        left = ttk.Frame(top, style="Card.TFrame")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8), pady=4)

        self.queue_notebook = ttk.Notebook(left)
        self.queue_notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.tab_queue_active = ttk.Frame(self.queue_notebook, style="Card.TFrame")
        self.queue_notebook.add(self.tab_queue_active, text="Cola principal")

        self.tab_queue_skipped = ttk.Frame(self.queue_notebook, style="Card.TFrame")
        self.queue_notebook.add(self.tab_queue_skipped, text="Omitidos / Errores")

        self.lista = tk.Listbox(self.tab_queue_active, selectmode=tk.EXTENDED, bg="#F9FBFF", fg="#1F2A44", selectbackground="#2D9CDB", selectforeground="#FFFFFF", relief=tk.FLAT, font=("Consolas", 10), height=12)
        self.lista.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 8))

        acciones = tk.Frame(self.tab_queue_active, bg="#FFFFFF")
        acciones.pack(fill=tk.X, padx=12, pady=(0, 10))

        self._btn(acciones, "Agregar", self.seleccionar_archivos, "#2F80ED").pack(side=tk.LEFT, padx=3)
        self._btn(acciones, "Cargar carpeta", self.cargar_carpeta, "#2F80ED").pack(side=tk.LEFT, padx=3)
        self._btn(acciones, "Quitar sel.", self.eliminar_seleccionados, "#F2994A").pack(side=tk.LEFT, padx=3)
        self._btn(acciones, "Limpiar", self.limpiar_lista, "#EB5757").pack(side=tk.LEFT, padx=3)
        tk.Checkbutton(acciones, text="Buscar recursivo", variable=self.var_recursivo, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=8)

        self.lista_omitidos = tk.Listbox(self.tab_queue_skipped, selectmode=tk.EXTENDED, bg="#FFF9F9", fg="#8B0000", selectbackground="#EB5757", selectforeground="#FFFFFF", relief=tk.FLAT, font=("Consolas", 10), height=12)
        self.lista_omitidos.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 8))

        acciones_omitidos = tk.Frame(self.tab_queue_skipped, bg="#FFFFFF")
        acciones_omitidos.pack(fill=tk.X, padx=12, pady=(0, 10))

        self._btn(acciones_omitidos, "Reincorporar", self.reincorporar_omitidos, "#27AE60").pack(side=tk.LEFT, padx=3)
        self._btn(acciones_omitidos, "Quitar sel.", self.eliminar_omitidos_seleccionados, "#F2994A").pack(side=tk.LEFT, padx=3)
        self._btn(acciones_omitidos, "Limpiar", self.limpiar_omitidos, "#EB5757").pack(side=tk.LEFT, padx=3)

        right = ttk.Frame(top, style="Card.TFrame")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=4)

        ttk.Label(right, text="Opciones de Procesamiento", style="CardTitle.TLabel").pack(anchor=tk.W, padx=12, pady=(10, 6))

        tab_divider = tk.Frame(right, height=1, bg="#E5ECF9")
        tab_divider.pack(fill=tk.X, padx=12, pady=(0, 10))

        modules_container = tk.Frame(right, bg="#FFFFFF")
        modules_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        m1_frame = tk.LabelFrame(modules_container, text="Procesar Videos", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57", padx=12, pady=10)
        m1_frame.pack(fill=tk.X, pady=(0, 12))
        tk.Label(m1_frame, text="Procesa los videos de la cola aplicando combinaciones de pistas y formatos.", font=("Segoe UI", 9), bg="#FFFFFF", fg="#5C6B8A").pack(anchor=tk.W, pady=(0, 8))
        m1_btns = tk.Frame(m1_frame, bg="#FFFFFF")
        m1_btns.pack(anchor=tk.W)
        self.btn_procesar_cola = self._btn(m1_btns, "Procesar cola", self.procesar_cola, "#2D9CDB")
        self.btn_procesar_cola.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_verificar = self._btn(m1_btns, "Verificar cola", self.verificar_condiciones_carpeta, "#27AE60")
        self.btn_verificar.pack(side=tk.LEFT)

        m3_frame = tk.LabelFrame(modules_container, text="Mantenimiento", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57", padx=12, pady=10)
        m3_frame.pack(fill=tk.X, pady=(0, 12))
        tk.Label(m3_frame, text="Herramientas de modificación in-place para los archivos originales de la cola.", font=("Segoe UI", 9), bg="#FFFFFF", fg="#5C6B8A").pack(anchor=tk.W, pady=(0, 8))
        m3_btns = tk.Frame(m3_frame, bg="#FFFFFF")
        m3_btns.pack(anchor=tk.W)
        self.btn_eliminar_meta = self._btn(m3_btns, "Eliminar meta", self.eliminar_metadatos, "#F2C94C")
        self.btn_eliminar_meta.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_eliminar_subs = self._btn(m3_btns, "Eliminar subs", self.eliminar_subtitulos, "#F2994A")
        self.btn_eliminar_subs.pack(side=tk.LEFT)
        self.btn_renombrar = self._btn(m3_btns, "Renombrar", self.abrir_renombrador, "#2D9CDB")
        self.btn_renombrar.pack(side=tk.LEFT, padx=(8, 0))

        cancel_frame = tk.Frame(modules_container, bg="#FFFFFF")
        cancel_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        self.btn_cancelar = self._btn(cancel_frame, "Cancelar todo", self.cancelar, "#EB5757")
        self.btn_cancelar.config(state=tk.DISABLED)
        self.btn_cancelar.pack(anchor=tk.W)

        opts_card = ttk.Frame(main, style="Card.TFrame")
        opts_card.pack(fill=tk.X, padx=18, pady=(2, 4))

        row1 = tk.Frame(opts_card, bg="#FFFFFF")
        row1.pack(fill=tk.X, padx=12, pady=(6, 2))
        tk.Label(row1, text="1. Salida:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        tk.Entry(row1, textvariable=self.salida_var, bg="#F4F8FF", fg="#1F2A44", relief=tk.FLAT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self._btn(row1, "Seleccionar", self.seleccionar_directorio, "#4DA8DA").pack(side=tk.LEFT)

        row2 = tk.Frame(opts_card, bg="#FFFFFF")
        row2.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(row2, text="2. Subcarpeta:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        tk.Checkbutton(row2, text="Crear", variable=self.var_subcarpeta, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=(0, 6))

        try:
            presets_data = json.loads(self.config_ini.get("Options", "presets", fallback='[]'))
        except Exception:
            presets_data = []
        self.cb_nombre_subcarpeta = ttk.Combobox(row2, textvariable=self.var_nombre_subcarpeta, values=presets_data, width=32)
        self.cb_nombre_subcarpeta.pack(side=tk.LEFT, padx=(0, 6))

        btn_build = self._btn(row2, "Configurar", self._abrir_constructor_rutas, "#2D9CDB")
        btn_build.pack(side=tk.LEFT)

        row3 = tk.Frame(opts_card, bg="#FFFFFF")
        row3.pack(fill=tk.X, padx=12, pady=(2, 6))

        tk.Label(row3, text="3. Opciones:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(row3, text="GPU:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(6, 2))
        self.cb_gpu = ttk.Combobox(row3, values=["NVIDIA (NVENC)", "Intel (QSV)", "AMD (AMF)"], state="readonly", width=32)
        self.cb_gpu.pack(side=tk.LEFT, padx=4)
        self.cb_gpu.bind("<<ComboboxSelected>>", self._on_gpu_selected)

        tk.Label(row3, text="Decod.:", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(6, 2))
        self.cb_decod = ttk.Combobox(row3, values=["Software", "D3D11VA", "DXVA2"], state="readonly", textvariable=self.decod_hw_var, width=8)
        self.cb_decod.pack(side=tk.LEFT, padx=4)

        tk.Checkbutton(row3, text="Sufijo al nombre", variable=self.var_sufijo_idiomas, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=6)
        tk.Checkbutton(row3, text="Eliminar metadatos al finalizar", variable=self.var_eliminar_metadatos, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=6)
        tk.Checkbutton(row3, text="Preservar color (BT.709)", variable=self.var_preservar_color, bg="#FFFFFF", fg="#2B3A57", activebackground="#FFFFFF", selectcolor="#FFFFFF").pack(side=tk.LEFT, padx=6)

        activity_card = ttk.Frame(main, style="Card.TFrame")
        activity_card.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 14))

        prog = tk.Frame(activity_card, bg="#FFFFFF")
        prog.pack(fill=tk.X, padx=12, pady=(8, 4))
        self.progress_label = tk.Label(prog, text="Listo", bg="#FFFFFF", fg="#5C6B8A", font=("Segoe UI", 9))
        self.progress_label.pack(anchor=tk.W)
        self.progress = ttk.Progressbar(prog, style="Modern.Horizontal.TProgressbar", mode="determinate")
        self.progress.pack(fill=tk.X, pady=(4, 0))

        tk.Label(activity_card, text="Actividad", bg="#FFFFFF", fg="#2B3A57", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=12, pady=(4, 0))
        log_frame = tk.Frame(activity_card, bg="#FFFFFF")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 8))
        self.log = tk.Text(log_frame, bg="#F9FBFF", fg="#24324A", font=("Consolas", 9), relief=tk.FLAT, state=tk.DISABLED, height=18)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scr = tk.Scrollbar(log_frame, command=self.log.yview)
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.config(yscrollcommand=scr.set)

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

        self._actualizar_contadores_colas()

    def _actualizar_contadores_colas(self):
        cant_activos = len([f for f in self.lista.get(0, tk.END) if f and str(f).strip()])
        cant_omitidos = len([f for f in self.lista_omitidos.get(0, tk.END) if f and str(f).strip()])
        try:
            self.queue_notebook.tab(self.tab_queue_active, text=f"Cola principal ({cant_activos})")
            self.queue_notebook.tab(self.tab_queue_skipped, text=f"Omitidos / Errores ({cant_omitidos})")
        except Exception:
            pass
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
                        ok = msg[1]
                        fail = msg[2]
                        errores = msg[3] if len(msg) > 3 else []
                        fue_cancelado = msg[4] if len(msg) > 4 else False
                        archivos_exitosos = msg[5] if len(msg) > 5 else []

                        self.progress["value"] = 100
                        if fue_cancelado:
                            self.progress_label.config(text=f"Cancelado | Exitos: {ok} | Fallos: {fail}")
                        else:
                            self.progress_label.config(text=f"Completado | Exitos: {ok} | Fallos: {fail}")
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

                            self._actualizar_contadores_colas()

                            if failed_files_norm:
                                self.queue_notebook.select(self.tab_queue_skipped)

                        self._limpiar_subgrupos()

                        title = "Proceso cancelado" if fue_cancelado else "Completado"
                        desc = "El procesamiento fue cancelado por el usuario." if fue_cancelado else "Proceso terminado."
                        messagebox.showinfo(title, f"{desc}\n\nExitos: {ok}\nFallos: {fail}")

                        total = ok + fail
                        if total > 1 and fail > 0 and errores:
                            self._mostrar_resumen_errores(errores)
                    elif msg[0] == "SELECTOR_PISTAS":
                        _, info, filename, q = msg
                        if self.cancelar_procesamiento:
                            q.put({"ok": False, "audio": None, "subtitle": None, "aplicar_todos": False})
                        else:
                            q.put(self._mostrar_selector_pistas(info, filename))
                    elif msg[0] == "SELECTOR_COMBINACIONES":
                        _, info, filename, subgrupo_label, q = msg
                        if self.cancelar_procesamiento:
                            q.put({"ok": False, "combinaciones": [], "aplicar_todos": False})
                        else:
                            q.put(self._mostrar_selector_combinaciones(info, filename, subgrupo_label))
                else:
                    self._append_log(msg)
        except queue.Empty:
            pass

        if self.procesando or not self.msg_queue.empty():
            self.root.after(100, self._actualizar_ui)

    def _mover_a_omitidos(self, archivos):
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

        self._actualizar_contadores_colas()
        self.queue_notebook.select(self.tab_queue_skipped)

    def reincorporar_omitidos(self):
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

        self._actualizar_contadores_colas()
        self._limpiar_subgrupos()
        self.queue_notebook.select(self.tab_queue_active)

    def eliminar_omitidos_seleccionados(self):
        sel = self.lista_omitidos.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona elementos en la lista de omitidos", parent=self.root)
            return
        for i in reversed(sel):
            self.lista_omitidos.delete(i)
        self._actualizar_contadores_colas()

    def limpiar_omitidos(self):
        if self.lista_omitidos.size() == 0:
            return
        if messagebox.askyesno("Confirmar", "Deseas limpiar todos los archivos omitidos?", parent=self.root):
            self.lista_omitidos.delete(0, tk.END)
            self._actualizar_contadores_colas()

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
            self._enviar_mensaje(f"Error ffprobe: {result.stderr[:220]}")
            return None

        try:
            data = json.loads(result.stdout)
            if "streams" not in data:
                return None
            if hasattr(self, "ffprobe_cache"):
                self.ffprobe_cache[filepath] = data
            return data
        except json.JSONDecodeError:
            return None

    def _invalidar_cache_archivo(self, filepath):
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

    def _obtener_firma_idiomas(self, info):
        if not info or "streams" not in info:
            return ((), ())
        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
        audio_langs = tuple((s.get("tags") or {}).get("language", "und").lower() for s in audio_streams)
        sub_langs = tuple((s.get("tags") or {}).get("language", "und").lower() for s in subtitle_streams)
        return (audio_langs, sub_langs)

    def _formatear_resumen_idiomas(self, langs, max_items=5):
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

    def _encontrar_firma_compatible(self, firma):
        if hasattr(self, "combinaciones_por_grupo") and firma in self.combinaciones_por_grupo:
            return firma
        return None

    def _verificar_ffmpeg_inicio(self):
        if not (self.ffmpeg_path and os.path.exists(self.ffmpeg_path)):
            self.ffmpeg_path = resolver_ruta_binario("ffmpeg.exe")
        if not (self.ffprobe_path and os.path.exists(self.ffprobe_path)):
            self.ffprobe_path = resolver_ruta_binario("ffprobe.exe")

        if os.path.exists(self.ffmpeg_path) and os.path.exists(self.ffprobe_path):
            self._actualizar_configuracion()
            return

        messagebox.showwarning(
            "FFmpeg/FFprobe no encontrados",
            "No se detectaron ffmpeg.exe y ffprobe.exe automáticamente.\n\n"
            "Puedes colocarlos en la carpeta 'tools/' junto a VW para modo portátil o seleccionarlos manualmente.",
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
                return self._mostrar_selector_pistas(info, filename)
        return resultado

    def _mostrar_selector_combinaciones(self, info, filename, subgrupo_label=None, modo_previo=False):
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

        resultado = {"ok": False, "combinaciones": [], "aplicar_todos": False}
        combinaciones = []

        if subgrupo_label:
            tk.Label(dialog, text=subgrupo_label, font=("Segoe UI", 11, "bold"), fg="#2D9CDB", wraplength=860, justify=tk.CENTER).pack(pady=(8, 2))
            tk.Label(dialog, text="Marca las pistas deseadas y pulsa Aceptar (o agrégalas como versiones múltiples).", font=("Segoe UI", 9)).pack(pady=(0, 6))
        else:
            tk.Label(dialog, text="Marca las pistas deseadas y pulsa Aceptar", font=("Segoe UI", 10, "bold")).pack(pady=8)

        # Empaquetar la barra inferior primero para garantizar que los botones Aceptar/Cancelar nunca queden fuera de pantalla
        bottom = tk.Frame(dialog)
        bottom.pack(side=tk.BOTTOM, pady=10)

        apply_all = tk.BooleanVar(value=True if modo_previo else False)
        chk_text = "Aplicar esta configuración a todos los archivos de este subgrupo" if modo_previo else "Aplicar esta configuración a todos los similares (mismo subgrupo)"
        tk.Checkbutton(dialog, text=chk_text, variable=apply_all).pack(side=tk.BOTTOM, pady=(0, 4))

        body = tk.Frame(dialog)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(2, 0))

        left = tk.LabelFrame(body, text="Pistas disponibles")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        var_hardsub = tk.BooleanVar(value=False)
        cb_hardsub = tk.Checkbutton(left, text="Hacer hardsub (Incrustar)", variable=var_hardsub, font=("Segoe UI", 9, "bold"), fg="#E74C3C", activeforeground="#E74C3C", state=tk.DISABLED)
        cb_hardsub.pack(side=tk.BOTTOM, anchor=tk.W, padx=8, pady=(4, 6))

        tracks_container = tk.Frame(left)
        tracks_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(tracks_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tracks_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollable_frame = tk.Frame(canvas)
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

        def actualizar_estado_hardsub():
            aud_sel = [s for v, s in audio_vars if v.get()]
            sub_sel = [s for v, s in sub_vars if v.get()]
            if len(aud_sel) == 1 and len(sub_sel) == 1:
                cb_hardsub.config(state=tk.NORMAL)
            else:
                var_hardsub.set(False)
                cb_hardsub.config(state=tk.DISABLED)

        tk.Label(scrollable_frame, text="Audio", fg="#1E8449", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=6, pady=(6, 2))
        for i, s in enumerate(audio_streams):
            tags = s.get("tags") or {}
            title = tags.get("title") or f"Audio {i + 1}"
            lang = tags.get("language", "und")
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_: actualizar_estado_hardsub())
            audio_vars.append((var, s))
            tk.Checkbutton(scrollable_frame, text=f"{title} ({lang})", variable=var, anchor=tk.W).pack(fill=tk.X, padx=8, pady=2)

        tk.Label(scrollable_frame, text="Subtitulos", fg="#2980B9", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=6, pady=(8, 2))
        for i, s in enumerate(subtitle_streams):
            tags = s.get("tags") or {}
            title = tags.get("title") or f"Sub {i + 1}"
            lang = tags.get("language", "und")
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_: actualizar_estado_hardsub())
            sub_vars.append((var, s))
            tk.Checkbutton(scrollable_frame, text=f"{title} ({lang})", variable=var, anchor=tk.W).pack(fill=tk.X, padx=8, pady=2)

        dialog.after(50, _actualizar_scroll_combos)

        right = tk.LabelFrame(body, text="Versiones a generar")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

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

        bt = tk.Frame(right)
        bt.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=6)
        tk.Button(bt, text="Agregar versión adicional", command=agregar, bg="#27AE60", fg="white").pack(side=tk.LEFT, padx=4)
        tk.Button(bt, text="Quitar", command=quitar, bg="#EB5757", fg="white").pack(side=tk.LEFT, padx=4)

        lst = tk.Listbox(right, font=("Consolas", 9))
        lst.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

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
                self._limpiar_subgrupos()
                resultado["ok"] = False
            elif ans is False:
                resultado["ok"] = False
            else:
                if self.cancelar_procesamiento:
                    return resultado
                return self._mostrar_selector_combinaciones(info, filename, subgrupo_label)
        return resultado

    def _obtener_combinaciones_a_generar(self, info, filename):
        if self.cancelar_procesamiento:
            return None

        firma = self._obtener_firma_idiomas(info)

        signature_match = self._encontrar_firma_compatible(firma)
        if signature_match:
            self._enviar_mensaje(f"  -> Aplicando configuración previamente guardada para el grupo de idiomas.")
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
        audio_langs_str = self._formatear_resumen_idiomas(firma[0])
        sub_langs_str = self._formatear_resumen_idiomas(firma[1])
        subgrupo_label = f"Subgrupo {subgrupo_num} (Audio: {audio_langs_str} | Subs: {sub_langs_str})"

        self._enviar_mensaje(f"  -> Abriendo selección de versiones para el {subgrupo_label}...")

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

    def _generar_combinaciones(self, input_file, output_dir, info, combinaciones, errores):
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

            out_dir = Path(output_dir)
            if self.var_subcarpeta.get():
                patron = self._resolver_patron_subcarpeta(input_file, info, label, audio_indices, sub_indices)
                out_dir = out_dir / Path(patron)

            out_dir.mkdir(parents=True, exist_ok=True)
            suffix = f"_{label}" if self.var_sufijo_idiomas.get() else ""
            output_path = out_dir / f"{video_stem}{suffix}.mp4"
            self._invalidar_cache_archivo(output_path)

            if combo.get("hardsub"):
                gpu = self.gpu_acel_var.get()
                is_ok = self.gpu_availability.get(gpu, True)
                if not is_ok:
                    status = self.gpus_status.get(gpu, (False, "No disponible"))
                    err_msg = f"El codificador {gpu.upper()} no está disponible. Detalle: {status[1]}"
                    self._enviar_mensaje(f"Error: {err_msg}. Saltando hardsub.")
                    errores.append((input_file, f"Versión '{label}': {err_msg}"))
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
                            err_msg = f"Fallo al extraer subtítulo de la versión '{label}'."
                            self._enviar_mensaje(err_msg)
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

                    color_flags = []
                    if self.var_preservar_color.get():
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
                            *color_flags,
                            *audio_settings, "-movflags", "+faststart", "-y", str(output_path)
                        ]
                    else:
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_amf", "-quality", preset,
                            "-rc", "vbr_peak", "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *color_flags,
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

                        if self.var_eliminar_metadatos.get():
                            self._enviar_mensaje(f"Eliminando metadatos de {output_path.name}...")
                            self._eliminar_metadatos_archivo(output_path)
                    else:
                        err_detail = ""
                        if hasattr(result, "stderr") and result.stderr:
                            lines_err = [l.strip() for l in result.stderr.splitlines() if l.strip()]
                            if lines_err:
                                err_detail = f" Detalle: {' '.join(lines_err[-2:])}"
                        err_msg = f"Error de FFmpeg al codificar la versión hardsub (código de salida: {result.returncode}).{err_detail}"
                        self._enviar_mensaje(err_msg)
                        errores.append((input_file, f"Versión '{label}': {err_msg}"))
                        fail += 1
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
                    self._enviar_mensaje(f"Advertencia: {excluidos} subtítulos bitmap/no texto excluidos")

                video_streams = [s for s in info["streams"] if s.get("codec_type") == "video"]
                main_video_streams = [s for s in video_streams if not s.get("disposition", {}).get("attached_pic")]
                if not main_video_streams:
                    main_video_streams = video_streams

                cmd = [self.ffmpeg_path, "-i", input_file]
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

                for idx in sub_incluir:
                    cmd.extend(["-map", f"0:{idx}"])

                if sub_incluir:
                    cmd.extend(["-c:s", "mov_text"])

                cmd.extend(["-movflags", "+faststart", "-y", str(output_path)])

                self._enviar_mensaje(f"[{i}/{len(combinaciones)}] {output_path.name}")
                result = self._run_subprocess_cancellable(cmd)

                if result.returncode != 0 and sub_incluir:
                    self._enviar_mensaje("  -> Advertencia: Falló multiplexado de subtítulos en MP4. Reintentando remux sin subtítulos...")
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
                    cmd_fallback.extend(["-sn", "-movflags", "+faststart", "-y", str(output_path)])
                    result = self._run_subprocess_cancellable(cmd_fallback)
                    if result.returncode == 0:
                        sub_incluir = []

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

                    if self.var_eliminar_metadatos.get():
                        self._enviar_mensaje(f"Eliminando metadatos de {output_path.name}...")
                        self._eliminar_metadatos_archivo(output_path)
                else:
                    err_detail = ""
                    if hasattr(result, "stderr") and result.stderr:
                        lines = [l.strip() for l in result.stderr.splitlines() if l.strip()]
                        if lines:
                            err_detail = f" Detalle: {' '.join(lines[-2:])}"
                    err_msg = f"Error de FFmpeg al copiar/remuxear la versión (código de salida: {result.returncode}).{err_detail}"
                    self._enviar_mensaje(err_msg)
                    errores.append((input_file, f"Versión '{label}': {err_msg}"))
                    fail += 1

        return ok, fail

    def _eliminar_pistas_procesamiento(self, archivo, output_dir, errores):
        if self.cancelar_procesamiento:
            return False

        info = self._ffprobe_info(archivo)
        if info is None:
            err_msg = "No se pudo leer streams con ffprobe."
            self._enviar_mensaje(err_msg)
            errores.append((archivo, err_msg))
            return False

        if self.cancelar_procesamiento:
            return False

        v = sum(1 for s in info["streams"] if s.get("codec_type") == "video")
        if v < 1:
            err_msg = "El archivo no contiene ninguna pista de video."
            self._enviar_mensaje(err_msg)
            errores.append((archivo, err_msg))
            return False

        combinaciones = self._obtener_combinaciones_a_generar(info, archivo)
        if self.cancelar_procesamiento or combinaciones is None:
            if not self.cancelar_procesamiento:
                err_msg = "Se canceló la selección de combinaciones."
                self._enviar_mensaje(err_msg)
                errores.append((archivo, err_msg))
            return False

        return self._generar_combinaciones(archivo, output_dir, info, combinaciones, errores)

    def _limpiar_subgrupos(self):
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

    def _obtener_mapa_subgrupos(self, archivos):
        subgrupos_dict = {}
        subgrupo_counter = 1
        for archivo in archivos:
            info = self._ffprobe_info(archivo)
            if not info:
                continue
            firma = self._obtener_firma_idiomas(info)
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

    def _preconfigurar_subgrupos_cola(self, archivos, output_dir=None, forzar_reconfiguracion=False):
        subgrupos_list = self._obtener_mapa_subgrupos(archivos)
        if not subgrupos_list:
            self._limpiar_subgrupos()
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
            audio_langs_str = self._formatear_resumen_idiomas(firma[0])
            sub_langs_str = self._formatear_resumen_idiomas(firma[1])
            subgrupo_label = f"Subgrupo {sg['num']} de {total_sg} ({txt_archivos}) | Audio: {audio_langs_str} | Subs: {sub_langs_str}"

            while True:
                r = self._mostrar_selector_combinaciones(
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
                            self._limpiar_subgrupos()
                            return False
                        else:
                            ans_omitir = messagebox.askyesno(
                                "Omitir subgrupo",
                                f"¿Deseas omitir los {txt_archivos} correspondientes a este subgrupo y continuar con los demás?\n\n(Si eliges 'No', volverás a abrir la configuración de este subgrupo)",
                                parent=self.root
                            )
                            if ans_omitir:
                                self._mover_a_omitidos(sg["archivos"])
                                break
                            else:
                                continue
                    else:
                        self._limpiar_subgrupos()
                        return False

        return True

    def _thread_procesar_cola(self, archivos, output_dir):
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
                    firma = self._obtener_firma_idiomas(info)
                    if firma not in self.subgrupos:
                        self.subgrupos[firma] = subgrupo_counter
                        subgrupo_counter += 1

        ok = 0
        fail = 0
        total = len(archivos)
        errores = []
        self._enviar_mensaje("===== INICIO PROCESAMIENTO =====")

        fue_cancelado = False
        archivos_exitosos = []
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._enviar_mensaje("Cancelado por usuario")
                fue_cancelado = True
                break
            self.msg_queue.put(("PROGRESO", i, total))
            self._enviar_mensaje(f"Archivo {i}/{total}: {os.path.basename(archivo)}")
            result = self._eliminar_pistas_procesamiento(archivo, output_dir, errores)

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

        self._enviar_mensaje("===== FIN PROCESAMIENTO =====")
        self.msg_queue.put(("FINALIZADO", ok, fail, errores, fue_cancelado, archivos_exitosos))
        self.procesando = False
        self.cancelar_procesamiento = False
        self._limpiar_subgrupos()

    def procesar_cola(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return
        self._limpiar_subgrupos()
        output = self.salida_var.get().strip()
        if not output:
            messagebox.showerror("Error", "Selecciona un directorio de salida")
            return
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        def callback_iniciar(archivos_validos):
            ok = self._preconfigurar_subgrupos_cola(archivos_validos, output_dir=output, forzar_reconfiguracion=True)
            if not ok:
                self._limpiar_subgrupos()
                return

            archivos_a_procesar = [f for f in archivos_validos if f in set(self.lista.get(0, tk.END))]
            if not archivos_a_procesar:
                messagebox.showwarning("Cola vacía", "No quedan archivos para procesar.")
                self._limpiar_subgrupos()
                return

            self.archivos_en_proceso = list(archivos_a_procesar)
            self._clear_log_and_progress("Preparando procesamiento de cola...")
            self._set_running_state(True)
            threading.Thread(target=self._thread_procesar_cola, args=(archivos_a_procesar, output), daemon=True).start()
            self._actualizar_ui()

        self.pre_verificar_cola("procesar_cola", archivos, output, callback_iniciar)

    def pre_verificar_cola(self, tipo_proceso, archivos, output_dir, callback_exito):
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
                res = self._validar_archivo_pre_verificacion(archivo, tipo_proceso, output_dir, infos.get(archivo))
                resultados.append(res)

            progreso.destroy()
            self.root.after(0, lambda: self._procesar_resultados_pre_verificacion(resultados, tipo_proceso, archivos, callback_exito))

        threading.Thread(target=worker, daemon=True).start()

    def _validar_archivo_pre_verificacion(self, archivo, tipo_proceso, output_dir, info=None):
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

        video_stream = video_streams[0]
        pix_fmt = video_stream.get("pix_fmt", "")

        is_10bit = False
        if any(x in pix_fmt for x in ("10le", "10be", "12le", "12be", "16le", "10p", "12p")):
            is_10bit = True
        elif video_stream.get("bits_per_raw_sample") in ("10", "12", "16"):
            is_10bit = True

        is_hdr = False
        if video_stream.get("color_transfer") in ("smpte2084", "arib-std-b67") or video_stream.get("color_primaries") == "bt2020":
            is_hdr = True

        if tipo_proceso == "procesar_cola":
            if is_10bit or is_hdr:
                desc = []
                if is_10bit:
                    desc.append("10-bit")
                if is_hdr:
                    desc.append("HDR")
                res["has_warning"] = True
                if self.var_preservar_color.get():
                    res["warnings"].append(f"El video original es {' y '.join(desc)}. Se aplicará preservación de color BT.709 para evitar tonos lavados al hacer hardsub.")
                else:
                    res["warnings"].append(f"El video original es {' y '.join(desc)}. Si decides generar versiones con subtitulos incrustados (hardsub), los colores podrian verse lavados.")

            if any(s.get("codec_name", "").lower() in BITMAP_SUB_CODECS for s in subtitle_streams):
                res["has_warning"] = True
                res["warnings"].append("El archivo contiene subtitulos bitmap (PGS/DVD/etc.). La opcion de hacer hardsub (incrustacion) sobre estos subtitulos provocara un fallo.")

        return res

    def _procesar_resultados_pre_verificacion(self, resultados, tipo_proceso, archivos, callback_exito):
        con_errores = [r for r in resultados if r["has_error"]]
        con_advertencias = [r for r in resultados if r["has_warning"]]

        if not con_errores and not con_advertencias:
            callback_exito(archivos)
            return

        self._mostrar_reporte_pre_verificacion(resultados, tipo_proceso, archivos, callback_exito)

    def _mostrar_reporte_pre_verificacion(self, resultados, tipo_proceso, archivos, callback_exito):
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
                self.root.after(0, lambda: self._mover_a_omitidos(con_errores))

            if filtrados:
                callback_exito(filtrados)
            else:
                messagebox.showwarning("Cola vacia", "No quedan archivos validos para procesar tras excluir los errores.")

        def cmd_omitir_problemas():
            filtrados = [r["archivo"] for r in resultados if not r["has_error"] and not r["has_warning"]]
            dialog.destroy()

            con_problemas = [r["archivo"] for r in resultados if r["has_error"] or r["has_warning"]]
            if con_problemas:
                self.root.after(0, lambda: self._mover_a_omitidos(con_problemas))

            if filtrados:
                callback_exito(filtrados)
            else:
                messagebox.showwarning("Cola vacia", "No quedan archivos limpios sin advertencias ni errores para procesar.")

        def cmd_cancelar():
            self._limpiar_subgrupos()
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

    def verificar_condiciones_carpeta(self):
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

                res = self._validar_archivo_pre_verificacion(archivo, "procesar_cola", None)
                resultados.append(res)

            progreso.destroy()
            self.root.after(0, lambda: self._mostrar_resultados_verificacion(resultados))

        threading.Thread(target=worker, daemon=True).start()

    def _mostrar_resultados_verificacion(self, resultados):
        win = tk.Toplevel(self.root)
        win.title("Diagnóstico de la cola - VW")
        win.geometry("980x700")
        win.transient(self.root)
        win.configure(bg="#F3F7FF")

        header = tk.Frame(win, bg="#1C2541")
        header.pack(fill=tk.X)
        tk.Label(header, text="Diagnóstico e Integridad de Videos", bg="#1C2541", fg="white", font=("Segoe UI", 14, "bold")).pack(pady=(12, 4))
        tk.Label(header, text="Análisis de legibilidad, códecs, HDR y pistas de la cola activa.", bg="#1C2541", fg="#B0C4DE", font=("Segoe UI", 9)).pack(pady=(0, 12))

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        t_ok = tk.Frame(nb, bg="#FFFFFF")
        t_warn = tk.Frame(nb, bg="#FFFFFF")
        t_err = tk.Frame(nb, bg="#FFFFFF")

        saludables = [r for r in resultados if not r["has_error"] and not r["has_warning"]]
        advertencias = [r for r in resultados if r["has_warning"] and not r["has_error"]]
        errores = [r for r in resultados if r["has_error"]]

        nb.add(t_ok, text=f"Saludables ({len(saludables)})")
        nb.add(t_warn, text=f"Advertencias ({len(advertencias)})")
        nb.add(t_err, text=f"Errores/Inaccesibles ({len(errores)})")

        tx1 = tk.Text(t_ok, font=("Consolas", 9), relief=tk.FLAT, padx=10, pady=10)
        tx1.pack(fill=tk.BOTH, expand=True)
        for r in saludables:
            tx1.insert(tk.END, f"✅ {r['archivo']}\n")
        tx1.config(state=tk.DISABLED)

        tx2 = tk.Text(t_warn, font=("Segoe UI", 9), relief=tk.FLAT, padx=10, pady=10)
        tx2.pack(fill=tk.BOTH, expand=True)
        tx2.tag_config("title", font=("Segoe UI", 9, "bold"), spacing1=6)
        tx2.tag_config("detail", font=("Segoe UI", 9), foreground="#5C6B8A", lmargin1=15, lmargin2=15)
        for r in advertencias:
            tx2.insert(tk.END, f"⚠️ {r['basename']}\n", "title")
            tx2.insert(tk.END, f"Ruta: {r['archivo']}\n", "detail")
            for w in r["warnings"]:
                tx2.insert(tk.END, f"• {w}\n", "detail")
        tx2.config(state=tk.DISABLED)

        tx3 = tk.Text(t_err, font=("Segoe UI", 9), relief=tk.FLAT, fg="#EB5757", padx=10, pady=10)
        tx3.pack(fill=tk.BOTH, expand=True)
        tx3.tag_config("title", font=("Segoe UI", 9, "bold"), foreground="#EB5757", spacing1=6)
        tx3.tag_config("detail", font=("Segoe UI", 9), foreground="#7F8C8D", lmargin1=15, lmargin2=15)
        for r in errores:
            tx3.insert(tk.END, f"❌ {r['basename']}\n", "title")
            tx3.insert(tk.END, f"Ruta: {r['archivo']}\n", "detail")
            for e in r["errors"]:
                tx3.insert(tk.END, f"• {e}\n", "detail")
        tx3.config(state=tk.DISABLED)

        btm = tk.Frame(win, bg="#F3F7FF")
        btm.pack(fill=tk.X, padx=15, pady=(0, 15))

        tk.Button(
            btm,
            text="Cerrar",
            command=win.destroy,
            bg="#2D9CDB",
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=6,
            font=("Segoe UI", 9, "bold")
        ).pack(side=tk.RIGHT)

    def _eliminar_metadatos_archivo(self, video_file, errores=None):
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

        cmd = [
            self.ffmpeg_path,
            "-i",
            str(video_file),
            "-map",
            "0:v?",
            "-map",
            "0:a?",
        ]
        if sub_args != ["-sn"]:
            cmd.extend(["-map", "0:s?"])

        cmd.extend(["-c:v", "copy", *audio_args, *sub_args, "-map_metadata", "-1", "-y", str(temp_output)])

        try:
            res = self._run_subprocess_cancellable(cmd, stdout_devnull=True)
            if res.returncode != 0:
                cmd_fb = [
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
                    "-map_metadata",
                    "-1",
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
                self._invalidar_cache_archivo(video_file)
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

    def _thread_eliminar_metadatos(self, archivos):
        self.procesando = True
        self.cancelar_procesamiento = False

        ok = 0
        fail = 0
        total = len(archivos)
        errores = []
        self._enviar_mensaje("===== INICIO ELIMINACIÓN METADATOS =====")

        fue_cancelado = False
        archivos_exitosos = []
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._enviar_mensaje("Cancelado por usuario")
                fue_cancelado = True
                break
            self.msg_queue.put(("PROGRESO", i, total))
            self._enviar_mensaje(f"Eliminando metadatos {i}/{total}: {os.path.basename(archivo)}")
            result = self._eliminar_metadatos_archivo(archivo, errores)

            if self.cancelar_procesamiento:
                fue_cancelado = True
                errores = [err for err in errores if err[0] != archivo]
                break

            if result:
                archivos_exitosos.append(archivo)
                ok += 1
            else:
                fail += 1

        self._enviar_mensaje("===== FIN ELIMINACIÓN METADATOS =====")
        self.msg_queue.put(("FINALIZADO", ok, fail, errores, fue_cancelado, archivos_exitosos))
        self.procesando = False
        self.cancelar_procesamiento = False

    def eliminar_metadatos(self):
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
            threading.Thread(target=self._thread_eliminar_metadatos, args=(archivos_validos,), daemon=True).start()
            self._actualizar_ui()

        self.pre_verificar_cola("eliminar_metadatos", archivos, None, callback_iniciar)

    def _eliminar_subtitulos_archivo(self, video_file, errores=None):
        video_file = Path(video_file)
        info = self._ffprobe_info(video_file)
        if info is None:
            if errores is not None:
                errores.append((str(video_file), "No se pudo leer streams con ffprobe."))
            return False

        subtitle_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "subtitle"]
        if not subtitle_streams:
            self._enviar_mensaje("  -> El archivo no contiene subtítulos. Saltando.")
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
                self._invalidar_cache_archivo(video_file)
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

    def _thread_eliminar_subtitulos(self, archivos):
        self.procesando = True
        self.cancelar_procesamiento = False

        ok = 0
        fail = 0
        total = len(archivos)
        errores = []
        self._enviar_mensaje("===== INICIO ELIMINACIÓN DE SUBTÍTULOS =====")

        fue_cancelado = False
        archivos_exitosos = []
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._enviar_mensaje("Cancelado por usuario")
                fue_cancelado = True
                break
            self.msg_queue.put(("PROGRESO", i, total))
            self._enviar_mensaje(f"Eliminando subs {i}/{total}: {os.path.basename(archivo)}")
            result = self._eliminar_subtitulos_archivo(archivo, errores)

            if self.cancelar_procesamiento:
                fue_cancelado = True
                errores = [err for err in errores if err[0] != archivo]
                break

            if result:
                archivos_exitosos.append(archivo)
                ok += 1
            else:
                fail += 1

        self._enviar_mensaje("===== FIN ELIMINACIÓN DE SUBTÍTULOS =====")
        self.msg_queue.put(("FINALIZADO", ok, fail, errores, fue_cancelado, archivos_exitosos))
        self.procesando = False
        self.cancelar_procesamiento = False

    def eliminar_subtitulos(self):
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
            threading.Thread(target=self._thread_eliminar_subtitulos, args=(archivos_validos,), daemon=True).start()
            self._actualizar_ui()

        self.pre_verificar_cola("eliminar_subtitulos", archivos, None, callback_iniciar)

    def _obtener_atributos_archivo(self, filepath):
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

    def abrir_renombrador(self):
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
            self._guardar_configuracion()
            
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
                self._guardar_configuracion()
                
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

        style = ttk.Style()
        style.configure("Renamer.Treeview", background="#FFFFFF", foreground="#1F2A44", fieldbackground="#FFFFFF", rowheight=24, font=("Segoe UI", 9))
        style.map("Renamer.Treeview", background=[("selected", "#2D9CDB")], foreground=[("selected", "#FFFFFF")])
        style.configure("Renamer.Treeview.Heading", font=("Segoe UI", 9, "bold"))

        tree = ttk.Treeview(tree_container, columns=("original", "nuevo", "status"), show="headings", style="Renamer.Treeview")
        tree.heading("original", text="Ruta Original / Nombre")
        tree.heading("nuevo", text="Nombre Nuevo Propuesto")
        tree.heading("status", text="Estado / Alerta")

        tree.column("original", width=340, anchor="w")
        tree.column("nuevo", width=340, anchor="w")
        tree.column("status", width=160, anchor="w")

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(tree_container, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.config(yscrollcommand=scrollbar.set)

        tree.tag_configure("ok", foreground="#27AE60")
        tree.tag_configure("conflict", foreground="#F2994A", font=("Segoe UI", 9, "bold"))
        tree.tag_configure("error", foreground="#EB5757", font=("Segoe UI", 9, "bold"))
        tree.tag_configure("no_change", foreground="#7F8C8D")

        def _es_nombre_valido(nombre):
            if not nombre.strip():
                return False
            invalidos = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
            return not any(c in nombre for c in invalidos)

        def actualizar_preview(*_):
            for item in tree.get_children():
                tree.delete(item)

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
                    attrs = self._obtener_atributos_archivo(filepath)
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

                tree.insert("", tk.END, values=(filepath, new_name, status), tags=(tag,))

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

        btn_ok = tk.Button(btn_container, text="Aplicar Renombrado", command=lambda: self._ejecutar_renombrado(dialog, archivos, tree), bg="#27AE60", fg="white", width=22, relief=tk.FLAT, font=("Segoe UI", 10, "bold"), cursor="hand2")
        btn_ok.pack(side=tk.LEFT, padx=10)

        btn_cancel = tk.Button(btn_container, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=12, relief=tk.FLAT, font=("Segoe UI", 10, "bold"), cursor="hand2")
        btn_cancel.pack(side=tk.LEFT, padx=10)

    def _ejecutar_renombrado(self, dialog, archivos, tree):
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

        self._enviar_mensaje("===== INICIO RENOMBRADO DE ARCHIVOS =====")
        ok_count = 0
        fail_count = 0
        mapping_renombres = {}

        for item_id in items:
            original_path, proposed_name, status = tree.item(item_id, "values")

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
                self._invalidar_cache_archivo(original_path)
                self._enviar_mensaje(f"Renombrado con éxito:\n  De: {original_path}\n  A: {new_path}")
                mapping_renombres[original_path] = new_path
                ok_count += 1
            except Exception as exc:
                self._enviar_mensaje(f"Error al renombrar {os.path.basename(original_path)}: {exc}")
                mapping_renombres[original_path] = original_path
                fail_count += 1

        all_items = list(self.lista.get(0, tk.END))
        self.lista.delete(0, tk.END)
        for path in all_items:
            new_val = mapping_renombres.get(path, path)
            self.lista.insert(tk.END, os.path.normpath(new_val))
        self._actualizar_contadores_colas()

        self._enviar_mensaje("===== FIN RENOMBRADO DE ARCHIVOS =====")
        self._enviar_mensaje(f"Renombrados con éxito: {ok_count} | Errores: {fail_count}")

        dialog.destroy()
        messagebox.showinfo("Renombrado Finalizado", f"Se han renombrado {ok_count} archivos correctamente.\nErrores: {fail_count}")

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
        self._actualizar_contadores_colas()

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
        self._actualizar_contadores_colas()

        messagebox.showinfo("Carga finalizada", f"Se agregaron {len(encontrados)} archivo(s)")

    def eliminar_seleccionados(self):
        sel = self.lista.curselection()
        if not sel:
            messagebox.showwarning("Sin seleccion", "Selecciona elementos")
            return
        for i in reversed(sel):
            self.lista.delete(i)
        self._actualizar_contadores_colas()
        self._limpiar_subgrupos()

    def limpiar_lista(self):
        if self.lista.size() == 0:
            return
        if messagebox.askyesno("Confirmar", "Deseas limpiar toda la lista?"):
            self.lista.delete(0, tk.END)
            self._actualizar_contadores_colas()
            if hasattr(self, "ffprobe_cache"):
                self.ffprobe_cache.clear()
            self._limpiar_subgrupos()

    def seleccionar_directorio(self):
        dir_inicial = self.salida_var.get().strip() or obtener_directorio_videos_defecto()
        carpeta = filedialog.askdirectory(title="Seleccionar salida", initialdir=dir_inicial)
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
            resolved = self._resolver_patron_subcarpeta(f"C:/ruta/de/ejemplo/{video_name}.mp4", info, "ESP_subENG", audio_indices, sub_indices)
            self.var_nombre_subcarpeta.set(old_val)

            base_dir = self.salida_var.get().strip() or obtener_directorio_videos_defecto()
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
            self._limpiar_subgrupos()
            if self.proceso_actual:
                try:
                    self.proceso_actual.terminate()
                except Exception:
                    pass
            self.btn_cancelar.config(state=tk.DISABLED)
            self._enviar_mensaje("Solicitud de cancelacion enviada...")

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

    def cambiar_ruta_ffmpeg(self):
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
        self._actualizar_configuracion()
        self._iniciar_deteccion_gpus()

    def cambiar_ruta_ffprobe(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar ffprobe.exe",
            filetypes=[("FFProbe", "ffprobe.exe"), ("Todos", "*.*")],
            initialdir=os.path.dirname(self.ffprobe_path) if (self.ffprobe_path and os.path.exists(os.path.dirname(self.ffprobe_path))) else TOOLS_DIR,
        )
        if archivo:
            self.ffprobe_path = archivo
            self._actualizar_configuracion()
            messagebox.showinfo("Actualizado", f"FFProbe actualizado\n\n{archivo}")

    def ver_info_ffmpeg(self):
        messagebox.showinfo(
            "Rutas configuradas",
            f"FFmpeg:\n{self.ffmpeg_path}\n\nFFProbe:\n{self.ffprobe_path}\n\nConfiguracion VW:\n{CONFIG_DIR}\n\nCarpeta Tools (Portatil):\n{os.path.join(obtener_ruta_base_app(), 'tools')}",
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

    def mostrar_acerca_de(self):
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

        header_card = tk.Frame(dialog, bg="#F4F8FF", highlightthickness=1, highlightbackground="#D1E2FF", bd=0)
        header_card.pack(fill=tk.X, padx=18, pady=(12, 6))

        accent_bar = tk.Frame(header_card, width=4, bg="#2D9CDB")
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        text_container = tk.Frame(header_card, bg="#F4F8FF")
        text_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=16, pady=8)

        tk.Label(
            text_container,
            text="VW",
            font=("Segoe UI", 12, "bold"),
            fg="#1F2A44",
            bg="#F4F8FF"
        ).pack(side=tk.LEFT)

        tk.Label(
            text_container,
            text="  |  Acerca de la herramienta",
            font=("Segoe UI", 9),
            fg="#5C6B8A",
            bg="#F4F8FF"
        ).pack(side=tk.LEFT, padx=(4, 0))

        tk.Label(
            header_card,
            text=f"v{VERSION}",
            font=("Segoe UI", 9, "bold"),
            bg="#F4F8FF",
            fg="#2D9CDB"
        ).pack(side=tk.RIGHT, padx=16, pady=10)

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

    def _mostrar_resumen_errores(self, errores):
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

    def salir_aplicacion(self):
        if self.procesando and not messagebox.askyesno("Proceso activo", "Hay un proceso en curso. Salir de todos modos?"):
            return

        cant_activos, cant_omitidos = self._actualizar_contadores_colas()
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

        self._actualizar_configuracion()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = VWSuite()
    app.run()
