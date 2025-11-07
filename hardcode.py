import subprocess
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import tempfile
import threading
import queue
import configparser

# -----------------------------
# CONFIGURACIÓN
# -----------------------------
# Crear directorio de configuración en %APPDATA%
CONFIG_DIR = os.path.join(os.getenv('APPDATA'), 'Galleon', 'HST')
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, 'hardcode_config.ini')

# Valores por defecto
DEFAULT_CONFIG = {
    "Paths": {
        "ffmpeg": r"C:\Users\Gabriel\AppData\Local\JDownloader 2.0\tools\Windows\ffmpeg\x64\ffmpeg.exe",
        "ffprobe": r"C:\Users\Gabriel\AppData\Local\JDownloader 2.0\tools\Windows\ffmpeg\x64\ffprobe.exe",
        "output_dir": ""
    },
    "Options": {
        "usar_nvidia": "True",
        "buscar_recursivo": "True",
        "preset": "medium"  # Funciona tanto en NVIDIA como en QSV
    }
}

# Presets disponibles con sus descripciones
# Presets para NVIDIA NVENC
PRESETS_NVIDIA = {
    "default": {
        "nombre": "Default",
        "descripcion": "Balance entre calidad y velocidad (por defecto) - Equivalente: x264 medium",
        "velocidad": "⚡⚡☆",
        "calidad": "★★★☆"
    },
    "slow": {
        "nombre": "Slow (HQ)",
        "descripcion": "Mejor calidad, menor velocidad (más recursos GPU) - Equivalente: x264 slow",
        "velocidad": "⚡☆☆",
        "calidad": "★★★★"
    },
    "medium": {
        "nombre": "Medium",
        "descripcion": "Calidad intermedia - Equivalente: x264 fast–medium",
        "velocidad": "⚡⚡☆",
        "calidad": "★★★☆"
    },
    "fast": {
        "nombre": "Fast",
        "descripcion": "Más rápido, algo menos eficiente - Equivalente: x264 faster",
        "velocidad": "⚡⚡⚡",
        "calidad": "★★☆☆"
    },
    "hp": {
        "nombre": "HP (High Performance)",
        "descripcion": "Prioriza velocidad, menor eficiencia - Equivalente: x264 veryfast",
        "velocidad": "⚡⚡⚡⚡",
        "calidad": "★★☆☆"
    },
    "hq": {
        "nombre": "HQ (High Quality)",
        "descripcion": "Prioriza calidad, más lento - Equivalente: x264 medium–slow",
        "velocidad": "⚡☆☆",
        "calidad": "★★★★☆"
    },
    "bd": {
        "nombre": "BD (Blu-ray Disc)",
        "descripcion": "Optimizado para compatibilidad Blu-ray - Equivalente: x264 slow",
        "velocidad": "⚡☆☆",
        "calidad": "★★★★"
    },
    "ll": {
        "nombre": "LL (Low Latency)",
        "descripcion": "Menor latencia, ideal para streaming en vivo - Equivalente: x264 fast",
        "velocidad": "⚡⚡⚡",
        "calidad": "★★☆☆"
    },
    "llhq": {
        "nombre": "LLHQ (Low Latency HQ)",
        "descripcion": "Baja latencia + alta calidad - Equivalente: x264 fast–medium",
        "velocidad": "⚡⚡☆",
        "calidad": "★★★☆"
    },
    "llhp": {
        "nombre": "LLHP (Low Latency HP)",
        "descripcion": "Baja latencia + alto rendimiento - Equivalente: x264 faster",
        "velocidad": "⚡⚡⚡",
        "calidad": "★★☆☆"
    },
    "lossless": {
        "nombre": "Lossless",
        "descripcion": "Codificación sin pérdida (archivos muy grandes)",
        "velocidad": "⚡☆☆",
        "calidad": "★★★★★"
    }
}

# Presets para Intel Quick Sync (QSV)
PRESETS_QSV = {
    "veryfast": {
        "nombre": "Very Fast",
        "descripcion": "Máxima velocidad, menor compresión - Equivalente: x264 veryfast",
        "velocidad": "⚡⚡⚡⚡",
        "calidad": "★★☆☆"
    },
    "faster": {
        "nombre": "Faster",
        "descripcion": "Rápido - Equivalente: x264 faster",
        "velocidad": "⚡⚡⚡",
        "calidad": "★★☆☆"
    },
    "fast": {
        "nombre": "Fast",
        "descripcion": "Buen balance velocidad/calidad - Equivalente: x264 fast",
        "velocidad": "⚡⚡⚡",
        "calidad": "★★★☆"
    },
    "medium": {
        "nombre": "Medium",
        "descripcion": "Calidad algo mejor, más lento - Equivalente: x264 medium",
        "velocidad": "⚡⚡☆",
        "calidad": "★★★☆"
    },
    "slow": {
        "nombre": "Slow",
        "descripcion": "Mejor calidad, más lento - Equivalente: x264 slow",
        "velocidad": "⚡☆☆",
        "calidad": "★★★★"
    },
    "veryslow": {
        "nombre": "Very Slow",
        "descripcion": "Máxima calidad (en GPUs compatibles) - Equivalente: x264 veryslow",
        "velocidad": "⚡☆☆",
        "calidad": "★★★★★"
    }
}

def obtener_preset_valido(preset, usar_nvidia):
    """
    Valida y ajusta el preset según la GPU seleccionada.
    Si el preset no existe para la GPU actual, devuelve un preset compatible.
    """
    if usar_nvidia:
        # Verificar si el preset existe en NVIDIA
        if preset in PRESETS_NVIDIA:
            return preset
        # Si no existe, intentar mapear presets comunes de QSV a NVIDIA
        mapeo_qsv_a_nvenc = {
            "veryfast": "hp",
            "faster": "fast",
            "fast": "fast",
            "medium": "medium",
            "slow": "slow",
            "veryslow": "hq"
        }
        return mapeo_qsv_a_nvenc.get(preset, "default")
    else:
        # Verificar si el preset existe en QSV
        if preset in PRESETS_QSV:
            return preset
        # Si no existe, intentar mapear presets comunes de NVIDIA a QSV
        mapeo_nvenc_a_qsv = {
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
            "lossless": "veryslow"
        }
        return mapeo_nvenc_a_qsv.get(preset, "medium")

def cargar_configuracion():
    """Carga la configuración desde el archivo .ini o crea uno con valores por defecto."""
    config = configparser.ConfigParser()
    
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE, encoding='utf-8')
            print(f"✅ Configuración cargada desde {CONFIG_FILE}")
        except Exception as e:
            print(f"⚠️ Error leyendo configuración: {e}")
            crear_configuracion_por_defecto(config)
    else:
        print(f"📝 Creando archivo de configuración por defecto: {CONFIG_FILE}")
        crear_configuracion_por_defecto(config)
    
    return config

def crear_configuracion_por_defecto(config):
    """Crea el archivo de configuración con valores por defecto."""
    for section, options in DEFAULT_CONFIG.items():
        config[section] = options
    guardar_configuracion(config)

def guardar_configuracion(config):
    """Guarda la configuración en el archivo .ini."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            config.write(f)
        print(f"💾 Configuración guardada en {CONFIG_FILE}")
    except Exception as e:
        print(f"❌ Error guardando configuración: {e}")

def actualizar_configuracion():
    """Actualiza el archivo de configuración con los valores actuales."""
    try:
        preset_value = preset_actual.get() if preset_actual and hasattr(preset_actual, 'get') else 'medium'
        output_dir_value = salida.get() if 'salida' in globals() and salida and hasattr(salida, 'get') else ''
        
        config = configparser.ConfigParser()
        config['Paths'] = {
            'ffmpeg': FFMPEG_PATH,
            'ffprobe': FFPROBE_PATH,
            'output_dir': output_dir_value
        }
        config['Options'] = {
            'usar_nvidia': str(var_usar_nvidia.get()),
            'buscar_recursivo': str(var_recursivo.get()),
            'preset': preset_value
        }
        guardar_configuracion(config)
    except Exception as e:
        print(f"❌ Error guardando configuración: {e}")

def on_gpu_change(*args):
    """Ajusta el preset automáticamente cuando se cambia de GPU."""
    try:
        if not preset_actual or not hasattr(preset_actual, 'get'):
            return
        
        preset_actual_val = preset_actual.get()
        usar_nvidia = var_usar_nvidia.get()
        
        # Obtener el preset válido para la nueva GPU
        nuevo_preset = obtener_preset_valido(preset_actual_val, usar_nvidia)
        
        # Si el preset cambió, actualizarlo y notificar
        if nuevo_preset != preset_actual_val:
            preset_actual.set(nuevo_preset)
            gpu_nombre = "NVIDIA NVENC" if usar_nvidia else "Intel Quick Sync (QSV)"
            print(f"🔄 Preset ajustado de '{preset_actual_val}' a '{nuevo_preset}' para {gpu_nombre}")
    except Exception as e:
        print(f"⚠️ Error ajustando preset: {e}")

# Cargar configuración al inicio
config_ini = cargar_configuracion()

# Aplicar configuración cargada
FFMPEG_PATH = config_ini.get('Paths', 'ffmpeg', fallback=DEFAULT_CONFIG['Paths']['ffmpeg'])
FFPROBE_PATH = config_ini.get('Paths', 'ffprobe', fallback=DEFAULT_CONFIG['Paths']['ffprobe'])

# Variable global para el preset
preset_actual = None

# Cola para comunicación entre threads
mensaje_queue = queue.Queue()
procesando = False
cancelar_procesamiento = False

# Configuración global de pistas seleccionadas
pistas_config = {
    'audio_tag': None,
    'subtitle_tag': None,
    'aplicar_a_todos': False
}

# Configuración de GPU
usar_nvidia = True

# -----------------------------
# FUNCIONES AUXILIARES
# -----------------------------
def enviar_mensaje(mensaje):
    """Envía un mensaje a la interfaz gráfica."""
    mensaje_queue.put(mensaje)

def ffprobe_info(filepath):
    """Obtiene la información del archivo con ffprobe."""
    filepath = os.path.normpath(filepath)
    filepath = os.path.abspath(filepath)
    
    if len(filepath) > 260 and not filepath.startswith('\\\\?\\'):
        filepath = '\\\\?\\' + filepath
    
    enviar_mensaje(f"🔍 FFProbe analizando: {os.path.basename(filepath)}")
    
    cmd = [
        FFPROBE_PATH, "-v", "error", "-print_format", "json",
        "-show_streams", filepath
    ]
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode != 0:
        enviar_mensaje(f"❌ Error ejecutando ffprobe: {result.stderr[:200]}")
        return None
    
    try:
        data = json.loads(result.stdout)
        if "streams" not in data or len(data["streams"]) == 0:
            enviar_mensaje(f"❌ No se encontraron streams")
            return None
        
        video_count = sum(1 for s in data["streams"] if s.get("codec_type") == "video")
        audio_count = sum(1 for s in data["streams"] if s.get("codec_type") == "audio")
        sub_count = sum(1 for s in data["streams"] if s.get("codec_type") == "subtitle")
        enviar_mensaje(f"✅ Streams: {video_count}v, {audio_count}a, {sub_count}s")
        
        return data
    except json.JSONDecodeError as e:
        enviar_mensaje(f"❌ Error parseando JSON: {e}")
        return None

def obtener_identificador_pista(stream):
    """Obtiene un identificador único para una pista basado en sus características."""
    tags = stream.get('tags', {})
    lang = tags.get('language', 'und')
    title = tags.get('title', '')
    codec = stream.get('codec_name', 'unknown')
    
    # Crear identificador: lang|title|codec
    return f"{lang}|{title}|{codec}"

def encontrar_pista_por_identificador(streams, identificador, codec_type):
    """Encuentra una pista por su identificador."""
    # Si el identificador es "NINGUNO" o None, no hay pista que buscar
    if identificador == "NINGUNO" or identificador is None:
        return None
    
    partes_buscadas = identificador.split('|')
    lang_buscado, title_buscado, codec_buscado = partes_buscadas
    
    for stream in streams:
        if stream.get('codec_type') != codec_type:
            continue
        
        tags = stream.get('tags', {})
        lang = tags.get('language', 'und')
        title = tags.get('title', '')
        codec = stream.get('codec_name', 'unknown')
        
        # Buscar coincidencia exacta
        if lang == lang_buscado and title == title_buscado and codec == codec_buscado:
            return stream['index']
    
    # Si no hay coincidencia exacta, buscar por idioma y título
    for stream in streams:
        if stream.get('codec_type') != codec_type:
            continue
        
        tags = stream.get('tags', {})
        lang = tags.get('language', 'und')
        title = tags.get('title', '')
        
        if lang == lang_buscado and title == title_buscado:
            return stream['index']
    
    # Si aún no hay coincidencia, devolver la primera pista del tipo
    for stream in streams:
        if stream.get('codec_type') == codec_type:
            return stream['index']
    
    return None

def mostrar_selector_pistas(info, filename):
    """Muestra un diálogo para seleccionar pistas de audio y subtítulos."""
    audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
    
    # Si solo hay una pista de cada tipo, mostrar el selector de todos modos para dar la opción de no usar subtítulos
    if len(audio_streams) <= 1 and len(subtitle_streams) == 0:
        resultado = {'ok': True, 'audio': None, 'subtitle': None, 'aplicar_todos': False}
        if audio_streams:
            resultado['audio'] = obtener_identificador_pista(audio_streams[0])
        return resultado
    
    # Crear ventana de diálogo
    dialog = tk.Toplevel(root)
    dialog.title(f"Seleccionar pistas - {os.path.basename(filename)}")
    dialog.geometry("700x600")
    dialog.transient(root)
    dialog.grab_set()
    
    # Resultado de la selección
    resultado = {'ok': False, 'audio': None, 'subtitle': None, 'aplicar_todos': False}
    
    # Frame superior para título
    header_frame = tk.Frame(dialog)
    header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
    
    tk.Label(header_frame, text=f"Archivo: {os.path.basename(filename)}", 
             font=("Arial", 10, "bold")).pack()
    
    # Frame principal con scroll para selectores
    main_frame = tk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    # Selector de audio
    if len(audio_streams) > 1:
        tk.Label(main_frame, text=f"Selecciona una pista de audio ({len(audio_streams)} disponibles):", 
                 font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(5, 5))
        
        audio_var = tk.StringVar(value=obtener_identificador_pista(audio_streams[0]))
        
        audio_frame = tk.Frame(main_frame)
        audio_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        audio_canvas = tk.Canvas(audio_frame, height=180)
        audio_scrollbar = tk.Scrollbar(audio_frame, orient="vertical", command=audio_canvas.yview)
        audio_scrollable = tk.Frame(audio_canvas)
        
        audio_scrollable.bind(
            "<Configure>",
            lambda e: audio_canvas.configure(scrollregion=audio_canvas.bbox("all"))
        )
        
        audio_canvas.create_window((0, 0), window=audio_scrollable, anchor="nw")
        audio_canvas.configure(yscrollcommand=audio_scrollbar.set)
        
        for i, stream in enumerate(audio_streams):
            codec = stream.get('codec_name', 'unknown')
            channels = stream.get('channels', '?')
            lang = stream.get('tags', {}).get('language', 'und')
            title = stream.get('tags', {}).get('title', '')
            bitrate = stream.get('bit_rate', 'N/A')
            if bitrate != 'N/A':
                bitrate = f"{int(bitrate)//1000}kbps"
            
            identificador = obtener_identificador_pista(stream)
            
            # Crear etiqueta descriptiva
            if title:
                texto = f"🎵 {title} ({lang})"
            else:
                texto = f"🎵 Audio {i+1} ({lang})"
            
            texto += f"\n   {codec.upper()} | {channels}ch | {bitrate}"
            
            tk.Radiobutton(audio_scrollable, text=texto, variable=audio_var, 
                          value=identificador, anchor=tk.W, justify=tk.LEFT,
                          wraplength=650).pack(fill=tk.X, padx=5, pady=3)
        
        audio_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        audio_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        resultado['audio'] = audio_var
    else:
        resultado['audio'] = obtener_identificador_pista(audio_streams[0]) if audio_streams else None
    
    # Selector de subtítulos
    if len(subtitle_streams) >= 1:
        tk.Label(main_frame, text=f"Selecciona una pista de subtítulos ({len(subtitle_streams)} disponibles):", 
                 font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(15, 5))
        
        # Opción por defecto: primer subtítulo (o "ninguno" si se quiere agregar esa opción)
        subtitle_var = tk.StringVar(value=obtener_identificador_pista(subtitle_streams[0]))
        
        sub_frame = tk.Frame(main_frame)
        sub_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        sub_canvas = tk.Canvas(sub_frame, height=180)
        sub_scrollbar = tk.Scrollbar(sub_frame, orient="vertical", command=sub_canvas.yview)
        sub_scrollable = tk.Frame(sub_canvas)
        
        sub_scrollable.bind(
            "<Configure>",
            lambda e: sub_canvas.configure(scrollregion=sub_canvas.bbox("all"))
        )
        
        sub_canvas.create_window((0, 0), window=sub_scrollable, anchor="nw")
        sub_canvas.configure(yscrollcommand=sub_scrollbar.set)
        
        # Opción "Sin subtítulos"
        tk.Radiobutton(sub_scrollable, text="❌ Sin subtítulos (solo video + audio)", 
                      variable=subtitle_var, value="NINGUNO", anchor=tk.W, 
                      font=("Arial", 9, "bold"), fg="red").pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(sub_scrollable, text="─" * 80, fg="gray").pack(fill=tk.X, padx=5, pady=2)
        
        for i, stream in enumerate(subtitle_streams):
            codec = stream.get('codec_name', 'unknown')
            lang = stream.get('tags', {}).get('language', 'und')
            title = stream.get('tags', {}).get('title', '')
            
            identificador = obtener_identificador_pista(stream)
            
            # Crear etiqueta descriptiva
            if title:
                texto = f"📝 {title} ({lang})"
            else:
                texto = f"📝 Subtítulo {i+1} ({lang})"
            
            texto += f"\n   {codec.upper()}"
            
            tk.Radiobutton(sub_scrollable, text=texto, variable=subtitle_var, 
                          value=identificador, anchor=tk.W, justify=tk.LEFT,
                          wraplength=650).pack(fill=tk.X, padx=5, pady=3)
        
        sub_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sub_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        resultado['subtitle'] = subtitle_var
    else:
        resultado['subtitle'] = "NINGUNO"  # Sin subtítulos disponibles
    
    # Frame inferior fijo para checkbox y botones
    footer_frame = tk.Frame(dialog)
    footer_frame.pack(fill=tk.X, padx=10, pady=10, side=tk.BOTTOM)
    
    # Checkbox para aplicar a todos
    aplicar_todos_var = tk.BooleanVar(value=False)
    tk.Checkbutton(footer_frame, text="✓ Aplicar esta selección a todos los archivos de la cola", 
                   variable=aplicar_todos_var, font=("Arial", 9, "bold")).pack(pady=(0, 10))
    
    resultado['aplicar_todos_var'] = aplicar_todos_var
    
    # Botones
    button_frame = tk.Frame(footer_frame)
    button_frame.pack()
    
    def aceptar():
        resultado['ok'] = True
        if isinstance(resultado['audio'], tk.StringVar):
            resultado['audio'] = resultado['audio'].get()
        if isinstance(resultado['subtitle'], tk.StringVar):
            resultado['subtitle'] = resultado['subtitle'].get()
        resultado['aplicar_todos'] = aplicar_todos_var.get()
        dialog.destroy()
    
    def cancelar():
        resultado['ok'] = False
        dialog.destroy()
    
    tk.Button(button_frame, text="✓ Aceptar", command=aceptar, bg="green", fg="white", 
              font=("Arial", 10, "bold"), width=15, height=1).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="✗ Cancelar", command=cancelar, bg="red", fg="white", 
              font=("Arial", 10, "bold"), width=15, height=1).pack(side=tk.LEFT, padx=5)
    
    # Esperar a que se cierre el diálogo
    dialog.wait_window()
    
    return resultado

def obtener_pistas_seleccionadas(info, filename):
    """Obtiene los índices de audio y subtítulos a usar."""
    global pistas_config
    
    audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
    
    # Si ya se configuró para aplicar a todos, buscar las pistas correspondientes
    if pistas_config['aplicar_a_todos']:
        audio_index = encontrar_pista_por_identificador(info["streams"], pistas_config['audio_tag'], "audio")
        subtitle_index = encontrar_pista_por_identificador(info["streams"], pistas_config['subtitle_tag'], "subtitle")
        
        # Si encontramos el audio (subtitle puede ser None si eligió "sin subtítulos")
        if audio_index is not None:
            return audio_index, subtitle_index
        else:
            enviar_mensaje(f"⚠️ No se encontró pista de audio coincidente, mostrando selector...")
    
    # Si solo hay una pista de cada tipo, usar esas
    if len(audio_streams) == 1 and len(subtitle_streams) == 1:
        return audio_streams[0]['index'], subtitle_streams[0]['index']
    
    enviar_mensaje(f"📋 Múltiples pistas detectadas, esperando selección del usuario...")
    
    # Crear cola temporal para esta operación
    respuesta_queue = queue.Queue()
    
    # Mostrar selector en el hilo principal
    mensaje_queue.put(("SELECTOR_PISTAS", info, filename, respuesta_queue))
    
    # Esperar respuesta con timeout
    try:
        resultado = respuesta_queue.get(timeout=300)  # 5 minutos de timeout
        
        if resultado['ok']:
            if resultado['aplicar_todos']:
                pistas_config['audio_tag'] = resultado['audio']
                pistas_config['subtitle_tag'] = resultado['subtitle']
                pistas_config['aplicar_a_todos'] = True
                enviar_mensaje(f"✓ Configuración guardada para aplicar a todos los archivos")
            
            # Convertir identificadores a índices
            audio_index = encontrar_pista_por_identificador(info["streams"], resultado['audio'], "audio")
            subtitle_index = encontrar_pista_por_identificador(info["streams"], resultado['subtitle'], "subtitle")
            
            return audio_index, subtitle_index
        else:
            enviar_mensaje(f"✗ Selección cancelada por el usuario")
            return None, None
    except queue.Empty:
        enviar_mensaje(f"❌ Timeout esperando selección del usuario")
        return None, None

def hardcode_subtitulo(input_file, output_dir):
    """Aplica hardcode de subtítulo usando NVENC si está disponible."""
    input_file = os.path.abspath(os.path.normpath(input_file))
    
    original_path = input_file
    use_unc = False
    if len(input_file) > 260 and not input_file.startswith('\\\\?\\'):
        input_file = '\\\\?\\' + input_file
        use_unc = True
        enviar_mensaje(f"⚠️ Ruta larga detectada, usando formato UNC")
    
    enviar_mensaje(f"\n🔍 Verificando: {os.path.basename(original_path)}")
    
    if not os.path.exists(input_file):
        enviar_mensaje(f"❌ Archivo no encontrado")
        return False
    
    enviar_mensaje(f"✅ Archivo existe")
    
    info = ffprobe_info(input_file)
    if info is None:
        enviar_mensaje(f"⚠️ No se pudo obtener información del archivo")
        return False
    
    # Verificar que haya al menos 1 video y 1 audio (subtítulo es opcional)
    v = sum(1 for s in info["streams"] if s.get("codec_type") == "video")
    a = sum(1 for s in info["streams"] if s.get("codec_type") == "audio")
    s = sum(1 for s in info["streams"] if s.get("codec_type") == "subtitle")
    
    if v != 1 or a < 1:
        enviar_mensaje(f"⚠️ No cumple requisitos mínimos (1v,≥1a). Encontrado: {v}v,{a}a,{s}s")
        return False
    
    # Obtener pistas seleccionadas (con selector si hay múltiples)
    audio_index, subtitle_index = obtener_pistas_seleccionadas(info, original_path)
    
    if audio_index is None:
        enviar_mensaje(f"⚠️ Selección cancelada por el usuario")
        return False
    
    # Mostrar información de las pistas seleccionadas
    for stream in info["streams"]:
        if stream.get("index") == audio_index:
            title = stream.get('tags', {}).get('title', f"Audio {audio_index}")
            enviar_mensaje(f"🎵 Audio seleccionado: {title}")
        if subtitle_index is not None and stream.get("index") == subtitle_index:
            title = stream.get('tags', {}).get('title', f"Subtítulo {subtitle_index}")
            enviar_mensaje(f"📝 Subtítulo seleccionado: {title}")
    
    if subtitle_index is None:
        enviar_mensaje(f"📝 Sin subtítulos (solo video + audio)")
    
    # Detectar el codec de audio de la pista seleccionada
    audio_codec = None
    for stream in info["streams"]:
        if stream.get("codec_type") == "audio" and stream.get("index") == audio_index:
            audio_codec = stream.get("codec_name")
            break
    
    enviar_mensaje(f"🎵 Codec de audio: {audio_codec}")
    
    # Definir sufijo según si hay subtítulos o no
    base_name = os.path.basename(original_path)
    sufijo = "_hardcoded" if subtitle_index is not None else "_nosub"
    
    # Crear directorio de salida si no existe
    output_dir_path = Path(output_dir)
    try:
        output_dir_path.mkdir(parents=True, exist_ok=True)
        enviar_mensaje(f"📁 Directorio de salida verificado: {output_dir}")
    except Exception as e:
        enviar_mensaje(f"❌ Error creando directorio de salida: {e}")
        return False
    
    output_path = output_dir_path / (Path(base_name).stem + sufijo + ".mp4")

    temp_subtitle_path = None
    try:
        # Configurar audio
        if audio_codec == "flac":
            enviar_mensaje("⚠️ Convirtiendo FLAC a AAC...")
            audio_settings = ["-c:a", "aac", "-b:a", "320k"]
        else:
            audio_settings = ["-c:a", "copy"]
        
        # Si hay subtítulos, extraerlos o configurar filtro
        if subtitle_index is not None:
            # Siempre extraer subtítulos a archivo temporal (más compatible)
            enviar_mensaje("📝 Extrayendo subtítulos...")
            temp_subtitle = tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False, encoding='utf-8')
            temp_subtitle_path = temp_subtitle.name
            temp_subtitle.close()
            
            extract_cmd = [
                FFMPEG_PATH,
                "-i", input_file,
                "-map", f"0:{subtitle_index}",
                "-y", temp_subtitle_path
            ]
            
            extract_result = subprocess.run(extract_cmd, capture_output=True, text=True)
            if extract_result.returncode != 0:
                enviar_mensaje(f"❌ Error extrayendo subtítulos")
                return False
            
            enviar_mensaje(f"✅ Subtítulos extraídos")
            
            if not os.path.exists(temp_subtitle_path) or os.path.getsize(temp_subtitle_path) == 0:
                enviar_mensaje(f"❌ Archivo de subtítulos vacío")
                return False
            
            # Escapar ruta del archivo temporal para el filtro ass
            temp_subtitle_escaped = temp_subtitle_path.replace('\\', '/').replace(':', '\\:')
            video_filter = f"ass='{temp_subtitle_escaped}',format=yuv420p"
        else:
            # Sin subtítulos, solo convertir formato de color
            video_filter = "format=yuv420p"
        
        # Obtener preset configurado y validarlo según GPU
        preset_configurado = preset_actual.get()
        preset = obtener_preset_valido(preset_configurado, usar_nvidia)
        
        # Informar si el preset fue ajustado
        if preset != preset_configurado:
            enviar_mensaje(f"ℹ️ Preset '{preset_configurado}' ajustado a '{preset}' para la GPU actual")
        
        # Construir comando ffmpeg según GPU seleccionada
        if usar_nvidia:
            # Codificación con NVIDIA NVENC
            cmd = [
                FFMPEG_PATH,
                "-i", input_file,
                "-map", f"0:v:0",
                "-map", f"0:{audio_index}",
                "-vf", video_filter,
                "-c:v", "h264_nvenc",
                "-preset", preset,
                "-profile:v", "high",
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", "5M",
                "-maxrate", "8M",
                "-bufsize", "10M",
                *audio_settings,
                "-movflags", "+faststart",
                "-y", str(output_path)
            ]
            enviar_mensaje(f"\n🚀 Procesando con GPU NVIDIA (NVENC) - Preset: {preset}...")
        else:
            # Codificación con Intel Quick Sync o CPU
            cmd = [
                FFMPEG_PATH,
                "-i", input_file,
                "-map", f"0:v:0",
                "-map", f"0:{audio_index}",
                "-vf", video_filter,
                "-c:v", "h264_qsv",  # Intel Quick Sync
                "-preset", preset,
                "-global_quality", "23",
                "-look_ahead", "1",
                "-b:v", "5M",
                "-maxrate", "8M",
                "-bufsize", "10M",
                *audio_settings,
                "-movflags", "+faststart",
                "-y", str(output_path)
            ]
            enviar_mensaje(f"\n🚀 Procesando con Intel Quick Sync (QSV) - Preset: {preset}...")
        
        enviar_mensaje(f"⏳ Esto puede tardar varios minutos...")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            enviar_mensaje(f"✅ Guardado en: {output_path.name}\n")
            return True
        else:
            enviar_mensaje(f"❌ Error procesando el archivo")
            error_lines = [line for line in result.stderr.split('\n') if 'error' in line.lower()][:3]
            for line in error_lines:
                enviar_mensaje(f"   {line}")
            return False
    
    finally:
        if temp_subtitle_path is not None:
            try:
                if os.path.exists(temp_subtitle_path):
                    os.unlink(temp_subtitle_path)
            except:
                pass

def procesar_archivos_thread(archivos, output_dir):
    """Función que se ejecuta en un thread separado para procesar archivos."""
    global procesando, pistas_config, cancelar_procesamiento, usar_nvidia
    procesando = True
    cancelar_procesamiento = False
    
    # Capturar configuración de GPU al inicio
    usar_nvidia = var_usar_nvidia.get()
    
    # Resetear configuración de pistas
    pistas_config = {
        'audio_tag': None,
        'subtitle_tag': None,
        'aplicar_a_todos': False
    }
    
    total = len(archivos)
    exitosos = 0
    fallidos = 0
    cancelados = 0
    
    enviar_mensaje(f"{'='*60}")
    enviar_mensaje(f"Iniciando procesamiento de {total} archivo(s)")
    enviar_mensaje(f"{'='*60}\n")
    
    for i, archivo in enumerate(archivos, 1):
        # Verificar si se solicitó cancelar
        if cancelar_procesamiento:
            enviar_mensaje(f"\n⚠️ Procesamiento cancelado por el usuario")
            cancelados = total - i + 1
            break
        
        mensaje_queue.put(("PROGRESO", i, total))
        enviar_mensaje(f"\n📹 Archivo {i}/{total}: {os.path.basename(archivo)}")
        
        if hardcode_subtitulo(archivo, output_dir):
            exitosos += 1
        else:
            fallidos += 1
    
    enviar_mensaje(f"\n{'='*60}")
    if cancelar_procesamiento:
        enviar_mensaje(f"⚠️ Procesamiento cancelado!")
    else:
        enviar_mensaje(f"✅ Procesamiento completado!")
    enviar_mensaje(f"   Exitosos: {exitosos}")
    enviar_mensaje(f"   Fallidos: {fallidos}")
    if cancelados > 0:
        enviar_mensaje(f"   Cancelados: {cancelados}")
    enviar_mensaje(f"{'='*60}\n")
    
    mensaje_queue.put(("FINALIZADO", exitosos, fallidos))
    procesando = False
    cancelar_procesamiento = False

# -----------------------------
# INTERFAZ GRÁFICA
# -----------------------------
def seleccionar_archivos():
    archivos = filedialog.askopenfilenames(
        title="Seleccionar archivos de video",
        filetypes=[("Videos", "*.mp4 *.mkv *.mov *.avi *.flv *.webm *.ts *.m4v")]
    )
    for archivo in archivos:
        archivo_normalizado = os.path.normpath(archivo)
        lista.insert(tk.END, archivo_normalizado)

def cargar_carpeta():
    """Carga todos los archivos de video de una carpeta."""
    carpeta = filedialog.askdirectory(title="Seleccionar carpeta con videos")
    if not carpeta:
        return
    
    recursivo = var_recursivo.get()
    extensiones = ('.mp4', '.mkv', '.mov', '.avi', '.flv', '.webm', '.ts', '.m4v')
    
    archivos_encontrados = []
    
    if recursivo:
        for root, dirs, files in os.walk(carpeta):
            for file in files:
                if file.lower().endswith(extensiones):
                    archivo_completo = os.path.join(root, file)
                    archivos_encontrados.append(archivo_completo)
    else:
        for file in os.listdir(carpeta):
            archivo_completo = os.path.join(carpeta, file)
            if os.path.isfile(archivo_completo) and file.lower().endswith(extensiones):
                archivos_encontrados.append(archivo_completo)
    
    if archivos_encontrados:
        for archivo in archivos_encontrados:
            archivo_normalizado = os.path.normpath(archivo)
            lista.insert(tk.END, archivo_normalizado)
        messagebox.showinfo("Archivos cargados", f"Se encontraron {len(archivos_encontrados)} archivo(s) de video")
    else:
        messagebox.showinfo("Sin archivos", "No se encontraron archivos de video en la carpeta seleccionada.")

def eliminar_seleccionados():
    """Elimina los archivos seleccionados de la lista."""
    seleccion = lista.curselection()
    if not seleccion:
        messagebox.showwarning("Sin selección", "Selecciona al menos un archivo para eliminar.")
        return
    
    for index in reversed(seleccion):
        lista.delete(index)

def limpiar_lista():
    """Limpia toda la lista de archivos."""
    if lista.size() > 0:
        respuesta = messagebox.askyesno("Limpiar lista", "¿Estás seguro de que deseas limpiar toda la lista?")
        if respuesta:
            lista.delete(0, tk.END)

def seleccionar_directorio():
    carpeta = filedialog.askdirectory(title="Seleccionar carpeta de salida")
    if carpeta:
        salida.set(carpeta)

def cancelar():
    """Cancela el procesamiento actual."""
    global cancelar_procesamiento
    
    if procesando:
        respuesta = messagebox.askyesno("Cancelar procesamiento", 
                                        "¿Estás seguro de que deseas cancelar el procesamiento?\n\n"
                                        "El archivo actual se terminará de procesar, pero los siguientes se omitirán.")
        if respuesta:
            cancelar_procesamiento = True
            btn_cancelar.config(state=tk.DISABLED)
            enviar_mensaje("\n⚠️ Solicitando cancelación...")
    else:
        messagebox.showinfo("Sin procesamiento", "No hay ningún procesamiento en curso.")

def procesar():
    global procesando
    
    if procesando:
        messagebox.showwarning("Procesando", "Ya hay un procesamiento en curso.")
        return
    
    output_dir = salida.get()
    if not output_dir:
        messagebox.showerror("Error", "Selecciona un directorio de salida.")
        return

    archivos = list(lista.get(0, tk.END))
    if not archivos:
        messagebox.showerror("Error", "Selecciona al menos un archivo de video.")
        return
    
    # Limpiar el log
    log_text.config(state=tk.NORMAL)
    log_text.delete(1.0, tk.END)
    log_text.config(state=tk.DISABLED)
    
    # Resetear barra de progreso
    progress_bar["value"] = 0
    progress_label.config(text="Preparando...")
    
    # Deshabilitar botón de procesar y habilitar cancelar
    btn_procesar.config(state=tk.DISABLED)
    btn_cancelar.config(state=tk.NORMAL)
    
    # Iniciar thread de procesamiento
    thread = threading.Thread(target=procesar_archivos_thread, args=(archivos, output_dir), daemon=True)
    thread.start()
    
    # Iniciar actualización de UI
    actualizar_ui()

def actualizar_ui():
    """Actualiza la interfaz con mensajes del thread de procesamiento."""
    try:
        while True:
            msg = mensaje_queue.get_nowait()
            
            if isinstance(msg, tuple):
                if msg[0] == "PROGRESO":
                    _, actual, total = msg
                    porcentaje = (actual / total) * 100
                    progress_bar["value"] = porcentaje
                    progress_label.config(text=f"Procesando {actual}/{total} ({porcentaje:.1f}%)")
                elif msg[0] == "FINALIZADO":
                    _, exitosos, fallidos = msg
                    progress_bar["value"] = 100
                    progress_label.config(text=f"¡Completado! ✅ {exitosos} | ❌ {fallidos}")
                    btn_procesar.config(state=tk.NORMAL)
                    btn_cancelar.config(state=tk.DISABLED)
                    messagebox.showinfo("Completado", f"Procesamiento terminado.\n\nExitosos: {exitosos}\nFallidos: {fallidos}")
                elif msg[0] == "SELECTOR_PISTAS":
                    _, info, filename, respuesta_queue = msg
                    # Ejecutar el selector en el hilo principal (UI)
                    resultado = mostrar_selector_pistas(info, filename)
                    # Enviar respuesta de vuelta al thread de procesamiento
                    respuesta_queue.put(resultado)
            else:
                # Es un mensaje de texto
                log_text.config(state=tk.NORMAL)
                log_text.insert(tk.END, msg + "\n")
                log_text.see(tk.END)
                log_text.config(state=tk.DISABLED)
    except queue.Empty:
        pass
    
    # Continuar actualizando si hay procesamiento activo
    if procesando or not mensaje_queue.empty():
        root.after(100, actualizar_ui)

# -----------------------------
# INFORMACIÓN DEL PROGRAMA
# -----------------------------
PROGRAMA_NOMBRE = "HardCode Subtitle Tool"
PROGRAMA_VERSION = "1.0.0"
PROGRAMA_AUTOR = "Tu Nombre"  # Cambia esto por tu nombre
PROGRAMA_DESCRIPCION = """
HardCode Subtitle Tool es una herramienta para incrustar (hardcodear) 
subtítulos en archivos de video utilizando FFmpeg.

Características principales:
• Procesamiento con GPU NVIDIA (NVENC) o Intel Quick Sync (QSV)
• Soporte para múltiples pistas de audio y subtítulos
• Conversión automática de FLAC a AAC
• Procesamiento por lotes con barra de progreso
• Búsqueda recursiva en carpetas
• Opción de procesar sin subtítulos

Requisitos:
• FFmpeg con soporte para NVENC y/o QSV
• GPU NVIDIA (para NVENC) o Intel con Quick Sync (para QSV)
• Python 3.x con tkinter
"""

# -----------------------------
# FUNCIONES DE MENÚ
# -----------------------------
def salir_aplicacion():
    """Cierra la aplicación."""
    if procesando:
        respuesta = messagebox.askyesno("Procesamiento activo", 
                                        "Hay un procesamiento en curso.\n¿Estás seguro de que deseas salir?")
        if not respuesta:
            return
    # Guardar configuración antes de salir
    actualizar_configuracion()
    root.quit()
    root.destroy()

def cambiar_ruta_ffmpeg():
    """Permite cambiar la ruta de FFmpeg."""
    global FFMPEG_PATH, FFPROBE_PATH
    
    archivo = filedialog.askopenfilename(
        title="Seleccionar FFmpeg",
        filetypes=[("FFmpeg", "ffmpeg.exe"), ("Todos los archivos", "*.*")],
        initialdir=os.path.dirname(FFMPEG_PATH)
    )
    
    if archivo:
        FFMPEG_PATH = archivo
        # Intentar encontrar ffprobe en el mismo directorio
        ffprobe_path = os.path.join(os.path.dirname(archivo), "ffprobe.exe")
        if os.path.exists(ffprobe_path):
            FFPROBE_PATH = ffprobe_path
            messagebox.showinfo("Rutas actualizadas", 
                              f"FFmpeg: {FFMPEG_PATH}\n\nFFProbe: {FFPROBE_PATH}")
        else:
            messagebox.showinfo("Ruta actualizada", 
                              f"FFmpeg: {FFMPEG_PATH}\n\n⚠️ FFProbe no encontrado en el mismo directorio.")
        
        # Guardar configuración
        actualizar_configuracion()

def cambiar_ruta_ffprobe():
    """Permite cambiar la ruta de FFProbe."""
    global FFPROBE_PATH
    
    archivo = filedialog.askopenfilename(
        title="Seleccionar FFProbe",
        filetypes=[("FFProbe", "ffprobe.exe"), ("Todos los archivos", "*.*")],
        initialdir=os.path.dirname(FFPROBE_PATH)
    )
    
    if archivo:
        FFPROBE_PATH = archivo
        messagebox.showinfo("Ruta actualizada", f"FFProbe: {FFPROBE_PATH}")
        
        # Guardar configuración
        actualizar_configuracion()
        
        # Guardar configuración
        actualizar_configuracion()

def cambiar_preset():
    """Muestra un diálogo para cambiar el preset de codificación."""
    global preset_actual
    
    # Determinar qué GPU se está usando
    usar_nvidia_actual = var_usar_nvidia.get()
    
    # Seleccionar el conjunto de presets correspondiente
    if usar_nvidia_actual:
        presets_dict = PRESETS_NVIDIA
        gpu_nombre = "NVIDIA NVENC"
        gpu_color = "#76b900"  # Verde NVIDIA
    else:
        presets_dict = PRESETS_QSV
        gpu_nombre = "Intel Quick Sync (QSV)"
        gpu_color = "#0071c5"  # Azul Intel
    
    # Crear ventana de diálogo
    dialog = tk.Toplevel(root)
    dialog.title(f"Preset de Codificación - {gpu_nombre}")
    dialog.geometry("700x550")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()
    
    # Frame superior con título
    header_frame = tk.Frame(dialog, bg="#34495e", height=80)
    header_frame.pack(fill=tk.X)
    header_frame.pack_propagate(False)
    
    tk.Label(header_frame, text="⚙️ Preset de Codificación FFmpeg", 
             font=("Arial", 15, "bold"), bg="#34495e", fg="white").pack(pady=(12, 3))
    tk.Label(header_frame, text=f"GPU: {gpu_nombre}", 
             font=("Arial", 10), bg="#34495e", fg=gpu_color).pack(pady=(0, 12))
    
    # Frame principal de contenido
    content_frame = tk.Frame(dialog, bg="white")
    content_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
    
    # Label de instrucción
    tk.Label(content_frame, text="Selecciona un preset:", 
             font=("Arial", 10, "bold"), bg="white", fg="#2c3e50").pack(anchor=tk.W, pady=(0, 10))
    
    # Frame para el combobox
    combo_frame = tk.Frame(content_frame, bg="white")
    combo_frame.pack(fill=tk.X, pady=(0, 20))
    
    # Crear lista de opciones para el combobox con formato: "nombre_preset - Nombre"
    preset_options = []
    preset_map = {}  # Mapeo de texto mostrado a clave del preset
    
    for preset_key, info in presets_dict.items():
        display_text = f"{info['nombre']}"
        preset_options.append(display_text)
        preset_map[display_text] = preset_key
    
    # Variable para el combobox
    combo_var = tk.StringVar()
    
    # Encontrar el texto correspondiente al preset actual
    preset_actual_key = preset_actual.get()
    if preset_actual_key in presets_dict:
        combo_var.set(presets_dict[preset_actual_key]['nombre'])
    else:
        # Si no existe, usar el primero de la lista
        combo_var.set(preset_options[0] if preset_options else "")
    
    # Combobox estilo moderno
    combo = ttk.Combobox(combo_frame, textvariable=combo_var, values=preset_options,
                         state="readonly", font=("Arial", 11), width=45)
    combo.pack(fill=tk.X)
    
    # Frame para la información del preset seleccionado
    info_frame = tk.Frame(content_frame, bg="#f8f9fa", relief=tk.SOLID, borderwidth=1)
    info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    
    # Padding interno
    info_content = tk.Frame(info_frame, bg="#f8f9fa")
    info_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
    
    # Labels para mostrar la información (se actualizarán dinámicamente)
    nombre_label = tk.Label(info_content, text="", font=("Arial", 13, "bold"), 
                           bg="#f8f9fa", fg="#2c3e50", anchor="w")
    nombre_label.pack(fill=tk.X, pady=(0, 10))
    
    # Frame para indicadores de velocidad y calidad
    indicadores_frame = tk.Frame(info_content, bg="#f8f9fa")
    indicadores_frame.pack(fill=tk.X, pady=(0, 15))
    
    # Velocidad
    vel_container = tk.Frame(indicadores_frame, bg="#f8f9fa")
    vel_container.pack(side=tk.LEFT, padx=(0, 30))
    
    tk.Label(vel_container, text="Velocidad:", font=("Arial", 9, "bold"), 
             bg="#f8f9fa", fg="#7f8c8d").pack(anchor=tk.W)
    vel_value_label = tk.Label(vel_container, text="", font=("Arial", 12), 
                              bg="#f8f9fa", fg="#e67e22")
    vel_value_label.pack(anchor=tk.W)
    
    # Calidad
    cal_container = tk.Frame(indicadores_frame, bg="#f8f9fa")
    cal_container.pack(side=tk.LEFT)
    
    tk.Label(cal_container, text="Calidad:", font=("Arial", 9, "bold"), 
             bg="#f8f9fa", fg="#7f8c8d").pack(anchor=tk.W)
    cal_value_label = tk.Label(cal_container, text="", font=("Arial", 12), 
                              bg="#f8f9fa", fg="#f39c12")
    cal_value_label.pack(anchor=tk.W)
    
    # Separador
    tk.Frame(info_content, height=1, bg="#dee2e6").pack(fill=tk.X, pady=(0, 15))
    
    # Descripción
    tk.Label(info_content, text="Descripción:", font=("Arial", 9, "bold"), 
             bg="#f8f9fa", fg="#7f8c8d", anchor="w").pack(fill=tk.X, pady=(0, 5))
    
    desc_label = tk.Label(info_content, text="", font=("Arial", 10), 
                         bg="#f8f9fa", fg="#495057", anchor="w", 
                         justify=tk.LEFT, wraplength=580)
    desc_label.pack(fill=tk.BOTH, expand=True)
    
    def actualizar_info_preset(event=None):
        """Actualiza la información mostrada según el preset seleccionado."""
        selected_text = combo_var.get()
        if selected_text in preset_map:
            preset_key = preset_map[selected_text]
            info = presets_dict[preset_key]
            
            nombre_label.config(text=info['nombre'])
            vel_value_label.config(text=info['velocidad'])
            cal_value_label.config(text=info['calidad'])
            desc_label.config(text=info['descripcion'])
    
    # Vincular evento de cambio en el combobox
    combo.bind("<<ComboboxSelected>>", actualizar_info_preset)
    
    # Actualizar con el preset inicial
    actualizar_info_preset()
    
    # Frame inferior para botones
    footer_frame = tk.Frame(dialog, bg="white")
    footer_frame.pack(fill=tk.X, padx=30, pady=(0, 20))
    
    button_frame = tk.Frame(footer_frame, bg="white")
    button_frame.pack()
    
    def aceptar():
        selected_text = combo_var.get()
        if selected_text in preset_map:
            nuevo_preset = preset_map[selected_text]
            preset_actual.set(nuevo_preset)
            messagebox.showinfo("Preset actualizado", 
                              f"Preset cambiado a: {presets_dict[nuevo_preset]['nombre']}\n"
                              f"GPU: {gpu_nombre}")
            dialog.destroy()
    
    def cancelar_dialog():
        dialog.destroy()
    
    tk.Button(button_frame, text="✓ Aceptar", command=aceptar, bg="#27ae60", fg="white", 
              font=("Arial", 10, "bold"), width=12, height=1).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="✗ Cancelar", command=cancelar_dialog, bg="#95a5a6", fg="white", 
              font=("Arial", 10, "bold"), width=12, height=1).pack(side=tk.LEFT, padx=5)

def mostrar_acerca_de():
    """Muestra información sobre el programa."""
    acerca_ventana = tk.Toplevel(root)
    acerca_ventana.title(f"Acerca de {PROGRAMA_NOMBRE}")
    acerca_ventana.geometry("550x620")
    acerca_ventana.resizable(False, False)
    acerca_ventana.transient(root)
    acerca_ventana.grab_set()
    
    # Frame para logo
    logo_frame = tk.Frame(acerca_ventana, height=130, bg="#2c3e50")
    logo_frame.pack(fill=tk.X)
    logo_frame.pack_propagate(False)
    
    tk.Label(logo_frame, text="🎬", font=("Arial", 48), bg="#2c3e50", fg="white").pack(pady=30)
    
    # Frame principal con contenido
    main_frame = tk.Frame(acerca_ventana, bg="white")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Nombre del programa
    tk.Label(main_frame, text=PROGRAMA_NOMBRE, font=("Arial", 18, "bold"), 
             bg="white").pack(pady=(10, 5))
    
    # Versión
    tk.Label(main_frame, text=f"Versión {PROGRAMA_VERSION}", font=("Arial", 10), 
             bg="white", fg="gray").pack()
    
    # Autor
    tk.Label(main_frame, text=f"Desarrollado por: {PROGRAMA_AUTOR}", font=("Arial", 9), 
             bg="white").pack(pady=(10, 5))
    
    # Separador
    sep_frame = tk.Frame(main_frame, bg="white")
    sep_frame.pack(fill=tk.X, pady=15, padx=40)
    tk.Frame(sep_frame, height=1, bg="#bdc3c7").pack(fill=tk.X)
    
    # Descripción
    desc_frame = tk.Frame(main_frame, bg="white")
    desc_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 10))
    
    tk.Label(desc_frame, text=PROGRAMA_DESCRIPCION.strip(), font=("Arial", 9), 
             bg="white", justify=tk.LEFT, wraplength=460, anchor="n").pack()
    
    # Frame inferior para botón
    footer_frame = tk.Frame(acerca_ventana, bg="white")
    footer_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
    
    # Botón cerrar
    tk.Button(footer_frame, text="Cerrar", command=acerca_ventana.destroy, 
              bg="#3498db", fg="white", font=("Arial", 10, "bold"), width=15).pack(pady=5)

# -----------------------------
# UI
# -----------------------------
root = tk.Tk()
root.title(f"{PROGRAMA_NOMBRE} v{PROGRAMA_VERSION}")
root.geometry("900x680")

# Barra de menú
menubar = tk.Menu(root)
root.config(menu=menubar)

# Menú Archivo
menu_archivo = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Archivo", menu=menu_archivo)
menu_archivo.add_command(label="Salir", command=salir_aplicacion, accelerator="Alt+F4")

# Menú Configuración
menu_config = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Configuración", menu=menu_config)
menu_config.add_command(label="Cambiar ruta de FFmpeg...", command=cambiar_ruta_ffmpeg)
menu_config.add_command(label="Cambiar ruta de FFProbe...", command=cambiar_ruta_ffprobe)
menu_config.add_separator()
menu_config.add_command(label="Preset de codificación...", command=cambiar_preset)

# Menú Ayuda
menu_ayuda = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Ayuda", menu=menu_ayuda)
menu_ayuda.add_command(label="Acerca de...", command=mostrar_acerca_de, accelerator="F1")

# Bind para F1
root.bind("<F1>", lambda e: mostrar_acerca_de())

# Frame para lista de archivos
frame_lista = tk.Frame(root)
frame_lista.pack(pady=5, fill=tk.BOTH, expand=True)

tk.Label(frame_lista, text="Archivos de video:", font=("Arial", 10, "bold")).pack()
lista = tk.Listbox(frame_lista, selectmode=tk.EXTENDED, width=110, height=8)
lista.pack(pady=5, side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar_lista = tk.Scrollbar(frame_lista, orient=tk.VERTICAL, command=lista.yview)
scrollbar_lista.pack(side=tk.RIGHT, fill=tk.Y)
lista.config(yscrollcommand=scrollbar_lista.set)

# Frame para botones de archivos
frame_botones_archivos = tk.Frame(root)
frame_botones_archivos.pack(pady=5)

tk.Button(frame_botones_archivos, text="Agregar archivos", command=seleccionar_archivos, 
          width=20, font=("Arial", 9), relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=3)
tk.Button(frame_botones_archivos, text="Cargar carpeta", command=cargar_carpeta, 
          width=20, font=("Arial", 9), relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=3)
tk.Button(frame_botones_archivos, text="Eliminar seleccionados", command=eliminar_seleccionados, 
          width=20, font=("Arial", 9), relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=3)
tk.Button(frame_botones_archivos, text="Limpiar lista", command=limpiar_lista, 
          width=20, font=("Arial", 9), relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=3)

# Frame para opciones
frame_opciones = tk.Frame(root)
frame_opciones.pack(pady=8)

# Checkbox para búsqueda recursiva (cargado desde configuración)
var_recursivo = tk.BooleanVar(value=config_ini.getboolean('Options', 'buscar_recursivo'))
var_recursivo.trace_add('write', lambda *args: actualizar_configuracion())
check_recursivo = tk.Checkbutton(frame_opciones, text="Buscar en subcarpetas (recursivo)", 
                                 variable=var_recursivo, font=("Arial", 9), 
                                 selectcolor="#e8f4f8", activebackground="#f0f0f0")
check_recursivo.pack(side=tk.LEFT, padx=15)

# Separador visual
tk.Label(frame_opciones, text="|", font=("Arial", 12), fg="lightgray").pack(side=tk.LEFT, padx=5)

# Checkbox para usar GPU NVIDIA (cargado desde configuración)
var_usar_nvidia = tk.BooleanVar(value=config_ini.getboolean('Options', 'usar_nvidia'))

def on_nvidia_change(*args):
    """Callback cuando cambia el checkbox de NVIDIA."""
    on_gpu_change()
    actualizar_configuracion()

var_usar_nvidia.trace_add('write', on_nvidia_change)
check_nvidia = tk.Checkbutton(frame_opciones, text="Usar GPU NVIDIA (NVENC)", 
                              variable=var_usar_nvidia, font=("Arial", 9, "bold"), 
                              fg="#00aa00", selectcolor="#e8f8e8", activebackground="#f0f0f0")
check_nvidia.pack(side=tk.LEFT, padx=15)

tk.Label(frame_opciones, text="(Si está desactivado, usará Intel Quick Sync)", 
         font=("Arial", 8, "italic"), fg="gray").pack(side=tk.LEFT, padx=5)

# Inicializar preset después de crear las variables
preset_actual = tk.StringVar(value=config_ini.get('Options', 'preset', fallback='medium'))
preset_actual.trace_add('write', lambda *args: actualizar_configuracion())

# Frame para directorio de salida
frame_salida = tk.Frame(root)
frame_salida.pack(pady=5, fill=tk.X, padx=10)

tk.Label(frame_salida, text="Directorio de salida:").pack(side=tk.LEFT)
salida = tk.StringVar(value=config_ini.get('Paths', 'output_dir', fallback=''))
salida.trace_add('write', lambda *args: actualizar_configuracion())
tk.Entry(frame_salida, textvariable=salida, width=70).pack(side=tk.LEFT, padx=10)
tk.Button(frame_salida, text="Seleccionar", command=seleccionar_directorio).pack(side=tk.LEFT)

# Frame para progreso
frame_progreso = tk.Frame(root)
frame_progreso.pack(pady=10, fill=tk.X, padx=10)

progress_label = tk.Label(frame_progreso, text="Listo para procesar", font=("Arial", 9))
progress_label.pack()

progress_bar = ttk.Progressbar(frame_progreso, length=800, mode='determinate')
progress_bar.pack(pady=5)

# Log de procesamiento
tk.Label(root, text="Log de procesamiento:", font=("Arial", 10, "bold")).pack(pady=(10, 0))
frame_log = tk.Frame(root)
frame_log.pack(pady=5, fill=tk.BOTH, expand=True, padx=10)

log_text = tk.Text(frame_log, height=10, width=110, state=tk.DISABLED, bg="#f0f0f0", font=("Consolas", 9))
log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar_log = tk.Scrollbar(frame_log, orient=tk.VERTICAL, command=log_text.yview)
scrollbar_log.pack(side=tk.RIGHT, fill=tk.Y)
log_text.config(yscrollcommand=scrollbar_log.set)

# Frame para botones de acción
frame_botones_accion = tk.Frame(root)
frame_botones_accion.pack(pady=15)

# Botón de procesar
btn_procesar = tk.Button(frame_botones_accion, text="PROCESAR", command=procesar, 
                         bg="#28a745", fg="white", font=("Arial", 13, "bold"), 
                         height=2, width=18, relief=tk.RAISED, bd=3,
                         activebackground="#218838", activeforeground="white",
                         cursor="hand2")
btn_procesar.pack(side=tk.LEFT, padx=8)

# Botón de cancelar
btn_cancelar = tk.Button(frame_botones_accion, text="CANCELAR", command=cancelar, 
                         bg="#dc3545", fg="white", font=("Arial", 13, "bold"), 
                         height=2, width=18, state=tk.DISABLED, relief=tk.RAISED, bd=3,
                         activebackground="#c82333", activeforeground="white",
                         cursor="hand2", disabledforeground="#aaaaaa")
btn_cancelar.pack(side=tk.LEFT, padx=8)

root.mainloop()
