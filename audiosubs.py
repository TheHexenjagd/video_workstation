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
CONFIG_DIR = os.path.join(os.getenv('APPDATA'), 'Galleon', 'ASRT')
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, 'asrt_config.ini')

# Valores por defecto
DEFAULT_CONFIG = {
    "Paths": {
        "ffmpeg": r"C:\Users\Gabriel\AppData\Local\JDownloader 2.0\tools\Windows\ffmpeg\x64\ffmpeg.exe",
        "ffprobe": r"C:\Users\Gabriel\AppData\Local\JDownloader 2.0\tools\Windows\ffmpeg\x64\ffprobe.exe",
        "output_dir": ""
    },
    "Options": {
        "buscar_recursivo": "True",
        "backup_original": "True"
    }
}

# Configuración de pistas a eliminar
pistas_a_eliminar = {
    'audio': [],  # Lista de índices de audio a eliminar
    'subtitle': [],  # Lista de índices de subtítulos a eliminar
    'aplicar_a_todos': False
}

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
        output_dir_value = salida.get() if 'salida' in globals() and salida and hasattr(salida, 'get') else ''
        backup_value = var_backup.get() if 'var_backup' in globals() and var_backup and hasattr(var_backup, 'get') else True
        
        config = configparser.ConfigParser()
        config['Paths'] = {
            'ffmpeg': FFMPEG_PATH,
            'ffprobe': FFPROBE_PATH,
            'output_dir': output_dir_value
        }
        config['Options'] = {
            'buscar_recursivo': str(var_recursivo.get()),
            'backup_original': str(backup_value)
        }
        guardar_configuracion(config)
    except Exception as e:
        print(f"❌ Error guardando configuración: {e}")

# Cargar configuración al inicio
config_ini = cargar_configuracion()

# Aplicar configuración cargada
FFMPEG_PATH = config_ini.get('Paths', 'ffmpeg', fallback=DEFAULT_CONFIG['Paths']['ffmpeg'])
FFPROBE_PATH = config_ini.get('Paths', 'ffprobe', fallback=DEFAULT_CONFIG['Paths']['ffprobe'])

# Cola para comunicación entre threads
mensaje_queue = queue.Queue()
procesando = False
cancelar_procesamiento = False

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
    """Muestra un diálogo para seleccionar pistas de audio y subtítulos a ELIMINAR."""
    audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
    
    # Si no hay pistas para eliminar, no mostrar el selector
    if len(audio_streams) == 0 and len(subtitle_streams) == 0:
        resultado = {'ok': True, 'audio': [], 'subtitle': [], 'aplicar_todos': False}
        return resultado
    
    # Crear ventana de diálogo
    dialog = tk.Toplevel(root)
    dialog.title(f"Seleccionar pistas a ELIMINAR - {os.path.basename(filename)}")
    dialog.geometry("700x600")
    dialog.transient(root)
    dialog.grab_set()
    
    # Resultado de la selección
    resultado = {'ok': False, 'audio': [], 'subtitle': [], 'aplicar_todos': False}
    
    # Frame superior para título
    header_frame = tk.Frame(dialog)
    header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
    
    tk.Label(header_frame, text=f"Archivo: {os.path.basename(filename)}", 
             font=("Arial", 10, "bold")).pack()
    tk.Label(header_frame, text="Marca las pistas que deseas ELIMINAR", 
             font=("Arial", 9), fg="red").pack()
    
    # Frame principal con scroll para selectores
    main_frame = tk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    # Variables para checkboxes de audio
    audio_vars = []
    
    # Selector de audio
    if len(audio_streams) > 0:
        tk.Label(main_frame, text=f"Pistas de audio ({len(audio_streams)} disponibles):", 
                 font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(5, 5))
        
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
            
            var = tk.BooleanVar(value=False)
            audio_vars.append((var, identificador))
            
            tk.Checkbutton(audio_scrollable, text=texto, variable=var, 
                          anchor=tk.W, justify=tk.LEFT,
                          wraplength=650).pack(fill=tk.X, padx=5, pady=3)
        
        audio_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        audio_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        resultado['audio_vars'] = audio_vars
    
    # Variables para checkboxes de subtítulos
    subtitle_vars = []
    
    # Selector de subtítulos
    if len(subtitle_streams) > 0:
        tk.Label(main_frame, text=f"Pistas de subtítulos ({len(subtitle_streams)} disponibles):", 
                 font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(15, 5))
        
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
            
            var = tk.BooleanVar(value=False)
            subtitle_vars.append((var, identificador))
            
            tk.Checkbutton(sub_scrollable, text=texto, variable=var, 
                          anchor=tk.W, justify=tk.LEFT,
                          wraplength=650).pack(fill=tk.X, padx=5, pady=3)
        
        sub_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sub_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        resultado['subtitle_vars'] = subtitle_vars
    
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
        # Recopilar pistas de audio marcadas para eliminar
        resultado['audio'] = [ident for var, ident in audio_vars if var.get()]
        # Recopilar pistas de subtítulos marcadas para eliminar
        resultado['subtitle'] = [ident for var, ident in subtitle_vars if var.get()]
        resultado['aplicar_todos'] = aplicar_todos_var.get()
        dialog.destroy()
    
    def cancelar_dialog():
        resultado['ok'] = False
        dialog.destroy()
    
    tk.Button(button_frame, text="✓ Aceptar", command=aceptar, bg="green", fg="white", 
              font=("Arial", 10, "bold"), width=15, height=1).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="✗ Cancelar", command=cancelar_dialog, bg="red", fg="white", 
              font=("Arial", 10, "bold"), width=15, height=1).pack(side=tk.LEFT, padx=5)
    
    # Esperar a que se cierre el diálogo
    dialog.wait_window()
    
    return resultado

def obtener_pistas_a_eliminar(info, filename):
    """Obtiene los índices de audio y subtítulos a ELIMINAR."""
    global pistas_a_eliminar
    
    audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
    
    # Si ya se configuró para aplicar a todos, buscar las pistas correspondientes
    if pistas_a_eliminar['aplicar_a_todos']:
        audio_indices = []
        for tag in pistas_a_eliminar['audio']:
            idx = encontrar_pista_por_identificador(info["streams"], tag, "audio")
            if idx is not None:
                audio_indices.append(idx)
        
        subtitle_indices = []
        for tag in pistas_a_eliminar['subtitle']:
            idx = encontrar_pista_por_identificador(info["streams"], tag, "subtitle")
            if idx is not None:
                subtitle_indices.append(idx)
        
        return audio_indices, subtitle_indices
    
    enviar_mensaje(f"📋 Esperando selección de pistas a eliminar...")
    
    # Crear cola temporal para esta operación
    respuesta_queue = queue.Queue()
    
    # Mostrar selector en el hilo principal
    mensaje_queue.put(("SELECTOR_PISTAS", info, filename, respuesta_queue))
    
    # Esperar respuesta con timeout
    try:
        resultado = respuesta_queue.get(timeout=300)  # 5 minutos de timeout
        
        if resultado['ok']:
            if resultado['aplicar_todos']:
                pistas_a_eliminar['audio'] = resultado['audio']
                pistas_a_eliminar['subtitle'] = resultado['subtitle']
                pistas_a_eliminar['aplicar_a_todos'] = True
                enviar_mensaje(f"✓ Configuración guardada para aplicar a todos los archivos")
            
            # Convertir identificadores a índices
            audio_indices = []
            for tag in resultado['audio']:
                idx = encontrar_pista_por_identificador(info["streams"], tag, "audio")
                if idx is not None:
                    audio_indices.append(idx)
            
            subtitle_indices = []
            for tag in resultado['subtitle']:
                idx = encontrar_pista_por_identificador(info["streams"], tag, "subtitle")
                if idx is not None:
                    subtitle_indices.append(idx)
            
            return audio_indices, subtitle_indices
        else:
            enviar_mensaje(f"✗ Selección cancelada por el usuario")
            return None, None
    except queue.Empty:
        enviar_mensaje(f"❌ Timeout esperando selección del usuario")
        return None, None

def eliminar_pistas(input_file, output_dir):
    """Elimina pistas de audio y subtítulos seleccionadas del archivo de video."""
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
    
    # Verificar que haya al menos 1 video
    v = sum(1 for s in info["streams"] if s.get("codec_type") == "video")
    a = sum(1 for s in info["streams"] if s.get("codec_type") == "audio")
    s = sum(1 for s in info["streams"] if s.get("codec_type") == "subtitle")
    
    if v < 1:
        enviar_mensaje(f"⚠️ No se encontró pista de video. Encontrado: {v}v,{a}a,{s}s")
        return False
    
    enviar_mensaje(f"📊 Pistas encontradas: {v} video, {a} audio, {s} subtítulos")
    
    # Obtener pistas a eliminar (con selector si es necesario)
    audio_indices, subtitle_indices = obtener_pistas_a_eliminar(info, original_path)
    
    if audio_indices is None:
        enviar_mensaje(f"⚠️ Selección cancelada por el usuario")
        return False
    
    # Mostrar información de las pistas que se eliminarán
    if len(audio_indices) > 0:
        enviar_mensaje(f"🗑️ Pistas de audio a eliminar:")
        for idx in audio_indices:
            for stream in info["streams"]:
                if stream.get("index") == idx:
                    title = stream.get('tags', {}).get('title', f"Audio {idx}")
                    lang = stream.get('tags', {}).get('language', 'und')
                    enviar_mensaje(f"   - {title} ({lang})")
    else:
        enviar_mensaje(f"✓ No se eliminarán pistas de audio")
    
    if len(subtitle_indices) > 0:
        enviar_mensaje(f"�️ Pistas de subtítulos a eliminar:")
        for idx in subtitle_indices:
            for stream in info["streams"]:
                if stream.get("index") == idx:
                    title = stream.get('tags', {}).get('title', f"Subtítulo {idx}")
                    lang = stream.get('tags', {}).get('language', 'und')
                    enviar_mensaje(f"   - {title} ({lang})")
    else:
        enviar_mensaje(f"✓ No se eliminarán pistas de subtítulos")
    
    # Si no hay pistas para eliminar, omitir archivo
    if len(audio_indices) == 0 and len(subtitle_indices) == 0:
        enviar_mensaje(f"⚠️ No se seleccionaron pistas para eliminar, se omite el archivo")
        return True
    
    base_name = os.path.basename(original_path)
    sufijo = "_cleaned"
    
    # Crear directorio de salida si no existe
    output_dir_path = Path(output_dir)
    try:
        output_dir_path.mkdir(parents=True, exist_ok=True)
        enviar_mensaje(f"📁 Directorio de salida verificado: {output_dir}")
    except Exception as e:
        enviar_mensaje(f"❌ Error creando directorio de salida: {e}")
        return False
    
    output_path = output_dir_path / (Path(base_name).stem + sufijo + ".mp4")

    try:
        # Construir comando FFmpeg para copiar streams excepto los que se eliminan
        cmd = [FFMPEG_PATH, "-i", input_file]
        
        # Mapear todos los streams
        cmd.extend(["-map", "0"])
        
        # Eliminar pistas de audio seleccionadas
        for idx in audio_indices:
            cmd.extend(["-map", f"-0:{idx}"])
        
        # Eliminar pistas de subtítulos seleccionadas
        for idx in subtitle_indices:
            cmd.extend(["-map", f"-0:{idx}"])
        
        # Copiar todos los codecs (sin recodificar)
        cmd.extend([
            "-c", "copy",
            "-y", str(output_path)
        ])
        
        enviar_mensaje(f"\n🚀 Eliminando pistas seleccionadas...")
        enviar_mensaje(f"⏳ Procesando...")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            enviar_mensaje(f"✅ Guardado en: {output_path.name}")
            
            # Si está habilitada la opción de backup, mantener el original
            # Si no, eliminar el original (opcional)
            backup_enabled = var_backup.get() if 'var_backup' in globals() else True
            if not backup_enabled:
                try:
                    os.remove(input_file)
                    enviar_mensaje(f"�️ Archivo original eliminado")
                except Exception as e:
                    enviar_mensaje(f"⚠️ No se pudo eliminar el original: {e}")
            
            enviar_mensaje("")
            return True
        else:
            enviar_mensaje(f"❌ Error procesando el archivo")
            error_lines = [line for line in result.stderr.split('\n') if 'error' in line.lower()][:3]
            for line in error_lines:
                enviar_mensaje(f"   {line}")
            return False
    
    except Exception as e:
        enviar_mensaje(f"❌ Error: {e}")
        return False

def procesar_archivos_thread(archivos, output_dir):
    """Función que se ejecuta en un thread separado para procesar archivos."""
    global procesando, pistas_a_eliminar, cancelar_procesamiento
    procesando = True
    cancelar_procesamiento = False
    
    # Resetear configuración de pistas
    pistas_a_eliminar = {
        'audio': [],
        'subtitle': [],
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
        
        if eliminar_pistas(archivo, output_dir):
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
PROGRAMA_NOMBRE = "Audio & Subtitle Removal Tool (ASRT)"
PROGRAMA_VERSION = "2.0.0"
PROGRAMA_AUTOR = "Galleon"
PROGRAMA_DESCRIPCION = """
Audio & Subtitle Removal Tool es una herramienta para listar y eliminar
pistas de audio y subtítulos de archivos de video utilizando FFmpeg.

Características principales:
• Listado detallado de todas las pistas de audio y subtítulos
• Selección múltiple de pistas a eliminar
• Procesamiento por lotes con barra de progreso
• Búsqueda recursiva en carpetas
• Opción de backup automático del archivo original
• Sin recodificación: proceso rápido y sin pérdida de calidad

Requisitos:
• FFmpeg instalado en el sistema
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

def ver_info_ffmpeg():
    """Muestra información sobre las rutas de FFmpeg configuradas."""
    info_texto = f"""Rutas configuradas:

FFmpeg: {FFMPEG_PATH}

FFProbe: {FFPROBE_PATH}

Directorio de configuración:
{CONFIG_DIR}
"""
    messagebox.showinfo("Información de FFmpeg", info_texto)

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
menu_config.add_command(label="Ver información de FFmpeg...", command=ver_info_ffmpeg)

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

# Checkbox para hacer backup del original (cargado desde configuración)
var_backup = tk.BooleanVar(value=config_ini.getboolean('Options', 'backup_original', fallback=True))
var_backup.trace_add('write', lambda *args: actualizar_configuracion())
check_backup = tk.Checkbutton(frame_opciones, text="Mantener copia del archivo original (backup)", 
                              variable=var_backup, font=("Arial", 9), 
                              fg="#0066cc", selectcolor="#e8f8ff", activebackground="#f0f0f0")
check_backup.pack(side=tk.LEFT, padx=15)

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
