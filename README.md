# 🎬 HardCode Subtitle Tool

![Python Version](https://img.shields.io/badge/python-3.x-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)

**HardCode Subtitle Tool** es una aplicación de escritorio con interfaz gráfica para incrustar subtítulos permanentemente en archivos de video utilizando aceleración por hardware (GPU).

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Presets de Codificación](#-presets-de-codificación)
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

##  Solución de Problemas

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
