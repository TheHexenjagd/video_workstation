# 🎬 HardCode Subtitle Tool

![Python Version](https://img.shields.io/badge/python-3.x-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)

**HardCode Subtitle Tool** es una aplicación de escritorio con interfaz gráfica para incrustar subtítulos permanentemente en archivos de video utilizando aceleración por hardware (GPU).

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [Configuración](#-configuración)
- [Presets de Codificación](#-presets-de-codificación)
- [Capturas de Pantalla](#-capturas-de-pantalla)
- [Solución de Problemas](#-solución-de-problemas)
- [Contribuciones](#-contribuciones)
- [Licencia](#-licencia)

## ✨ Características

### Principales
- ✅ **Aceleración por GPU**: Soporte para NVIDIA NVENC y Intel Quick Sync (QSV)
- 🎯 **Procesamiento por lotes**: Procesa múltiples archivos de video simultáneamente
- 🎵 **Selección de pistas**: Interfaz para elegir pistas de audio y subtítulos específicas
- 🔄 **Conversión automática**: Convierte FLAC a AAC cuando es necesario
- 📁 **Búsqueda recursiva**: Opción para buscar videos en subcarpetas
- 🚫 **Modo sin subtítulos**: Permite procesar solo video + audio sin incrustar subtítulos
- 📊 **Barra de progreso**: Visualización en tiempo real del procesamiento
- 💾 **Configuración persistente**: Guarda preferencias en `%APPDATA%\Galleon\HST`

### Funcionalidades Avanzadas
- Soporte para rutas largas (>260 caracteres) con formato UNC
- Sistema de logs detallado con información del procesamiento
- Cancelación de procesamiento en curso
- Presets de codificación optimizados para diferentes escenarios
- Detección automática de múltiples streams de audio/subtítulos
- Configuración de calidad y velocidad de codificación personalizable

## 🔧 Requisitos

### Software
- **Python 3.x** con Tkinter
- **FFmpeg** con soporte para:
  - `h264_nvenc` (para GPUs NVIDIA)
  - `h264_qsv` (para Intel Quick Sync)
- **FFProbe** (incluido con FFmpeg)

### Hardware
- **GPU NVIDIA** (serie GTX/RTX) con soporte NVENC, **O**
- **Procesador Intel** con Quick Sync Video (generaciones 2+)

### Formatos Soportados
**Entrada**: `.mp4`, `.mkv`, `.mov`, `.avi`, `.flv`, `.webm`, `.ts`, `.m4v`  
**Salida**: `.mp4` (H.264 + AAC)

## 📥 Instalación

### 1. Instalar Python
Descarga e instala Python 3.x desde [python.org](https://www.python.org/downloads/)

### 2. Instalar FFmpeg
Descarga FFmpeg desde [ffmpeg.org](https://ffmpeg.org/download.html) o utiliza una distribución como:
- [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
- [BtbN Builds](https://github.com/BtbN/FFmpeg-Builds/releases)

### 3. Clonar el Repositorio
```bash
git clone https://github.com/TheHexenjagd/galleon_mc_hardcodetool.git
cd galleon_mc_hardcodetool
```

### 4. Ejecutar la Aplicación
```bash
python hardcode.py
```

## 🚀 Uso

### Interfaz Gráfica

1. **Agregar Videos**
   - **Agregar archivos**: Selecciona videos individuales
   - **Cargar carpeta**: Carga todos los videos de una carpeta
   - **Búsqueda recursiva**: Activa para incluir subcarpetas

2. **Configurar Salida**
   - Selecciona el directorio donde se guardarán los videos procesados
   - Los archivos tendrán el sufijo `_hardcoded` o `_nosub`

3. **Seleccionar GPU**
   - ✅ **NVIDIA NVENC**: Para tarjetas gráficas NVIDIA
   - ⬜ **Intel Quick Sync**: Para procesadores Intel con iGPU

4. **Procesar**
   - Haz clic en **PROCESAR** para iniciar
   - Si hay múltiples pistas de audio/subtítulos, aparecerá un selector
   - Opción de aplicar la misma selección a todos los archivos

### Selector de Pistas

Cuando un video tiene múltiples pistas de audio o subtítulos:

```
🎵 Audio 1 (spa)
   AAC | 2ch | 128kbps

🎵 Audio 2 (eng)  
   DTS | 6ch | 1536kbps

📝 Subtítulo 1 (spa)
   SUBRIP

❌ Sin subtítulos (solo video + audio)
```

Marca **"✓ Aplicar esta selección a todos los archivos de la cola"** para usar las mismas pistas en todos los videos.

## ⚙️ Configuración

### Archivo de Configuración
La configuración se guarda automáticamente en:
```
%APPDATA%\Galleon\HST\hardcode_config.ini
```

### Estructura del Archivo
```ini
[Paths]
ffmpeg = C:\ruta\a\ffmpeg.exe
ffprobe = C:\ruta\a\ffprobe.exe
output_dir = C:\Videos\Salida

[Options]
usar_nvidia = True
buscar_recursivo = True
preset = medium
```

### Cambiar Rutas de FFmpeg
**Menú → Configuración → Cambiar ruta de FFmpeg/FFProbe**

### Cambiar Preset
**Menú → Configuración → Preset de codificación**

## 🎛️ Presets de Codificación

### NVIDIA NVENC

| Preset | Velocidad | Calidad | Descripción |
|--------|-----------|---------|-------------|
| `lossless` | ⚡☆☆ | ★★★★★ | Sin pérdida (archivos muy grandes) |
| `slow` | ⚡☆☆ | ★★★★ | Mejor calidad (~x264 slow) |
| `hq` | ⚡☆☆ | ★★★★☆ | Alta calidad (~x264 medium-slow) |
| `bd` | ⚡☆☆ | ★★★★ | Optimizado para Blu-ray |
| `default` | ⚡⚡☆ | ★★★☆ | Balance (~x264 medium) **[Recomendado]** |
| `medium` | ⚡⚡☆ | ★★★☆ | Calidad intermedia |
| `llhq` | ⚡⚡☆ | ★★★☆ | Baja latencia + HQ |
| `fast` | ⚡⚡⚡ | ★★☆☆ | Rápido (~x264 faster) |
| `ll` | ⚡⚡⚡ | ★★☆☆ | Baja latencia |
| `llhp` | ⚡⚡⚡ | ★★☆☆ | Baja latencia + HP |
| `hp` | ⚡⚡⚡⚡ | ★★☆☆ | Alto rendimiento (~x264 veryfast) |

### Intel Quick Sync (QSV)

| Preset | Velocidad | Calidad | Descripción |
|--------|-----------|---------|-------------|
| `veryslow` | ⚡☆☆ | ★★★★★ | Máxima calidad (~x264 veryslow) |
| `slow` | ⚡☆☆ | ★★★★ | Mejor calidad (~x264 slow) |
| `medium` | ⚡⚡☆ | ★★★☆ | Calidad intermedia **[Recomendado]** |
| `fast` | ⚡⚡⚡ | ★★★☆ | Buen balance |
| `faster` | ⚡⚡⚡ | ★★☆☆ | Rápido (~x264 faster) |
| `veryfast` | ⚡⚡⚡⚡ | ★★☆☆ | Máxima velocidad |

> **Nota**: Los presets se ajustan automáticamente al cambiar de GPU.

## 📸 Capturas de Pantalla

### Ventana Principal
```
┌─────────────────────────────────────────────────────────┐
│  Archivo  Configuración  Ayuda                          │
├─────────────────────────────────────────────────────────┤
│  Archivos de video:                                     │
│  ┌───────────────────────────────────────────────────┐  │
│  │ C:\Videos\Pelicula1.mkv                           │  │
│  │ C:\Videos\Pelicula2.mp4                           │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  [Agregar archivos] [Cargar carpeta] [Eliminar] [...]  │
│                                                          │
│  ☑ Buscar en subcarpetas | ☑ Usar GPU NVIDIA (NVENC)   │
│                                                          │
│  Directorio de salida: C:\Videos\Salida [Seleccionar]  │
│                                                          │
│  Listo para procesar                                    │
│  [████████████████████████████████████████] 100%        │
│                                                          │
│  Log de procesamiento:                                  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ ✅ Procesamiento completado!                      │  │
│  │    Exitosos: 2                                     │  │
│  │    Fallidos: 0                                     │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│         [   PROCESAR   ]    [   CANCELAR   ]            │
└─────────────────────────────────────────────────────────┘
```

## 🐛 Solución de Problemas

### Error: "No se encontró FFmpeg"
- Verifica la ruta en **Configuración → Cambiar ruta de FFmpeg**
- Asegúrate de que `ffmpeg.exe` y `ffprobe.exe` existan

### Error: "No se pudo codificar con NVENC"
- Verifica que tu GPU NVIDIA soporte NVENC
- Actualiza los drivers de NVIDIA
- Intenta cambiar a Intel Quick Sync si tienes procesador Intel

### Error: "Unknown encoder 'h264_nvenc'"
- Tu versión de FFmpeg no tiene soporte para NVENC
- Descarga una versión con soporte para hardware encoding

### Los subtítulos no se ven correctamente
- Algunos formatos de subtítulos complejos pueden tener problemas
- Prueba extrayendo y convirtiendo los subtítulos a `.ass` primero

### Procesamiento muy lento
- Selecciona un preset más rápido (`fast`, `hp`, `veryfast`)
- Verifica que estés usando aceleración por GPU
- Comprueba el uso de GPU en el Administrador de tareas

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Haz fork del proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Añadir nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🙏 Agradecimientos

- **FFmpeg** - Por la herramienta de procesamiento de video
- **NVIDIA** - Por la tecnología NVENC
- **Intel** - Por Quick Sync Video
- Comunidad de código abierto

---

**Desarrollado por Gabriel** | [GitHub](https://github.com/TheHexenjagd/galleon_mc_hardcodetool)

> 💡 **Tip**: Para mejores resultados, usa el preset `medium` con NVIDIA o `fast` con Intel QSV.
