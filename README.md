# 🎬 Audio & Subtitle Removal Tool (ASRT)

![Python Version](https://img.shields.io/badge/python-3.x-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)
![FFmpeg](https://img.shields.io/badge/FFmpeg-7.1%2B-orange.svg)

**Audio & Subtitle Removal Tool (ASRT)** es una aplicación de escritorio con interfaz gráfica para eliminar selectivamente pistas de audio y subtítulos de archivos de video sin recodificar, manteniendo la máxima calidad.

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [Configuración](#-configuración)
- [Solución de Problemas](#-solución-de-problemas)
- [Contribuciones](#-contribuciones)
- [Licencia](#-licencia)

## ✨ Características

### Principales
- 🗑️ **Eliminación selectiva**: Elige exactamente qué pistas de audio y subtítulos eliminar
- 🚀 **Sin recodificación**: Proceso ultra rápido sin pérdida de calidad (solo remux)
- 📊 **Análisis detallado**: Visualiza información completa de todas las pistas (codec, idioma, canales, bitrate)
- 📦 **Procesamiento por lotes**: Procesa múltiples archivos de video simultáneamente
- 📁 **Búsqueda recursiva**: Opción para buscar videos en subcarpetas
- 🔄 **Aplicar a todos**: Configura una vez y aplica la misma selección a toda la cola
- 💾 **Backup opcional**: Mantén el archivo original si lo deseas
- 📊 **Barra de progreso**: Visualización en tiempo real del procesamiento

### Funcionalidades Avanzadas
- ✅ **Configuración automática**: Detecta FFmpeg en primera ejecución
- 📂 **Rutas por defecto**: Busca automáticamente en `C:\Users\Gabriel\AppData\Roaming\Galleon\bin`
- 🔧 **Configuración persistente**: Guarda preferencias en `%APPDATA%\Galleon\ASRT`
- 🎯 **Identificación inteligente**: Sistema avanzado de identificación de pistas por idioma, título y codec
- 🛡️ **Rutas largas**: Soporte para rutas >260 caracteres con formato UNC
- ⚡ **Optimizado para FFmpeg 7.1+**: Preparado para las últimas características
- 🎮 **Soporte NVIDIA**: Listo para aceleración por hardware (futuras funciones de recodificación)
- 📋 **Logs detallados**: Sistema de mensajes con emojis para fácil seguimiento

## 🔧 Requisitos

### Software
- **Python 3.x** con Tkinter
- **FFmpeg 7.1+** (recomendado) o versiones anteriores
- **FFProbe** (incluido con FFmpeg)

### Hardware
- Cualquier PC con Windows
- **Opcional**: GPU NVIDIA para futuras funciones de recodificación

### Formatos Soportados
**Entrada**: `.mp4`, `.mkv`, `.mov`, `.avi`, `.flv`, `.webm`, `.ts`, `.m4v`, `.wmv`  
**Salida**: `.mp4` (sin recodificación, solo remuxing)

## 📥 Instalación

### 1. Instalar Python
Descarga e instala Python 3.x desde [python.org](https://www.python.org/downloads/)

> ⚠️ **Importante**: Marca la opción "Add Python to PATH" durante la instalación

### 2. Instalar FFmpeg

#### Opción A: Instalación Manual
1. Descarga FFmpeg desde [ffmpeg.org](https://ffmpeg.org/download.html) o [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
2. Extrae los archivos a `C:\Users\Gabriel\AppData\Roaming\Galleon\bin`
3. Asegúrate de que `ffmpeg.exe` y `ffprobe.exe` estén en ese directorio

#### Opción B: Usar FFmpeg existente
Si ya tienes FFmpeg instalado, la aplicación te pedirá ubicarlo en la primera ejecución

### 3. Clonar el Repositorio
```bash
git clone https://github.com/TheHexenjagd/galleon_mc_audiosubs_remover.git
cd galleon_mc_audiosubs_remover
```

### 4. Ejecutar la Aplicación
```bash
python audiosubs.py
```

## 🚀 Uso

### Primera Ejecución

En la primera ejecución, si FFmpeg no se encuentra en la ruta por defecto, aparecerá un diálogo:

```
⚠️ FFmpeg no encontrado en: C:\Users\Gabriel\AppData\Roaming\Galleon\bin\ffmpeg.exe
📁 Por favor, selecciona la ubicación de ffmpeg.exe
```

Navega hasta la ubicación de `ffmpeg.exe` y selecciónalo. El programa detectará automáticamente `ffprobe.exe` si está en la misma carpeta.

## ⚙️ Configuración

### Archivo de Configuración
La configuración se guarda automáticamente en:
```
%APPDATA%\Galleon\ASRT\asrt_config.ini
```

### Estructura del Archivo
```ini
[Paths]
ffmpeg = C:\Users\Gabriel\AppData\Roaming\Galleon\bin\ffmpeg.exe
ffprobe = C:\Users\Gabriel\AppData\Roaming\Galleon\bin\ffprobe.exe
output_dir = C:\Videos\Salida

[Options]
buscar_recursivo = True
backup_original = True
```


##  Solución de Problemas

### Error: "No se encontró FFmpeg"
**Causa**: FFmpeg no está en la ruta configurada

**Solución**:
1. Verifica la ruta en **Configuración → Cambiar ruta de FFmpeg**
2. Asegúrate de que `ffmpeg.exe` y `ffprobe.exe` existan
3. Descarga FFmpeg si no lo tienes instalado

### Error: "No se pudo obtener información del archivo"
**Causa**: El archivo puede estar corrupto o en un formato no soportado

**Solución**:
1. Verifica que el archivo sea un video válido
2. Intenta reproducir el archivo con VLC para confirmar que no está corrupto
3. Revisa el log para ver el mensaje de error específico de FFProbe

### El programa no encuentra archivos en la carpeta
**Causa**: Los archivos no tienen extensiones de video reconocidas

**Solución**:
- Las extensiones soportadas son: `.mp4`, `.mkv`, `.mov`, `.avi`, `.flv`, `.webm`, `.ts`, `.m4v`, `.wmv`
- Verifica que tus archivos tengan una de estas extensiones

### No aparece el selector de pistas
**Causa**: El video no tiene pistas de audio o subtítulos para eliminar

**Solución**:
- El selector solo aparece si hay pistas de audio o subtítulos
- Si el video solo tiene 1 audio y 0 subtítulos, no hay nada que eliminar

### Error: "Selección cancelada por el usuario"
**Causa**: Hiciste clic en Cancelar en el selector de pistas

**Solución**:
- Esto no es un error, simplemente cancela el procesamiento de ese archivo
- Vuelve a hacer clic en PROCESAR para intentar de nuevo

### Los archivos procesados son muy grandes
**Causa**: Esto no debería ocurrir con ASRT ya que no recodifica

**Solución**:
- El tamaño del archivo procesado debería ser similar o menor al original
- Si es significativamente mayor, puede haber un problema con FFmpeg
- Verifica que estés usando la versión más reciente de FFmpeg

### Error en rutas largas (>260 caracteres)
**Causa**: Windows tiene un límite de 260 caracteres para rutas

**Solución**:
- ASRT maneja esto automáticamente usando formato UNC (`\\?\`)
- Si aún tienes problemas, intenta mover los archivos a una ruta más corta

### La aplicación no inicia
**Causa**: Puede ser un problema con Tkinter o Python

**Solución**:
```bash
# Verifica que Python esté instalado
python --version

# Verifica que Tkinter esté disponible
python -c "import tkinter"

# Si Tkinter no está disponible, reinstala Python con la opción tcl/tk
```

### El procesamiento es lento
**Causa**: ASRT no recodifica, por lo que el procesamiento debería ser muy rápido

**Solución**:
- Si el procesamiento es lento, puede ser por:
  - Disco duro lento (HDD vs SSD)
  - Muchos archivos grandes
  - Rutas de red lentas
- El procesamiento típicamente toma menos de 30 segundos por archivo

## 🆚 Comparación con otras herramientas

| Característica | ASRT | MKVToolNix | HandBrake | Avidemux |
|----------------|------|------------|-----------|----------|
| Sin recodificación | ✅ | ✅ | ❌ | ✅ |
| Interfaz gráfica | ✅ | ✅ | ✅ | ✅ |
| Procesamiento por lotes | ✅ | ⚠️ | ✅ | ❌ |
| Selector visual de pistas | ✅ | ⚠️ | ✅ | ⚠️ |
| Aplicar a todos | ✅ | ❌ | ⚠️ | ❌ |
| Búsqueda recursiva | ✅ | ❌ | ❌ | ❌ |
| Verificación de condiciones | ✅ | ❌ | ❌ | ❌ |

**Leyenda**: ✅ Soportado | ⚠️ Parcial | ❌ No soportado

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Haz fork del proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Añadir nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

### Ideas para Contribuir
- 🌐 Internacionalización (i18n)
- 🎨 Temas personalizables (modo oscuro)
- 📊 Estadísticas de espacio ahorrado
- 🔄 Deshacer cambios
- 📝 Presets de configuración
- 🎬 Previsualización de pistas
- 🗜️ Compresión opcional con NVENC/QSV

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🙏 Agradecimientos

- **FFmpeg** - Por la increíble herramienta de procesamiento multimedia
- **NVIDIA** - Por la tecnología de aceleración por hardware
- Comunidad de código abierto
- Usuarios que reportan bugs y sugieren mejoras

## 📚 Recursos Adicionales

- [Documentación de FFmpeg](https://ffmpeg.org/documentation.html)
- [FFmpeg Wiki](https://trac.ffmpeg.org/wiki)
- [Formatos de subtítulos](https://en.wikipedia.org/wiki/Subtitle_(captioning)#Subtitle_formats)

## 🔄 Historial de Versiones

### v2.1.0 (2026-01-10)
- ✨ Nueva ruta por defecto: `C:\Users\Gabriel\AppData\Roaming\Galleon\bin`
- ✨ Verificación automática de FFmpeg en primera ejecución
- ✨ Optimizaciones para FFmpeg 7.1+
- ✨ Soporte mejorado para aceleración NVIDIA (futuras funciones)
- 🐛 Correcciones en el manejo de configuración
- 📝 Documentación mejorada

### v2.0.0
- 🎉 Lanzamiento inicial con interfaz gráfica completa
- ✨ Selector de pistas interactivo
- ✨ Procesamiento por lotes
- ✨ Verificación de condiciones de subtítulos
- ✨ Sistema de configuración persistente

---

**Desarrollado por Galleon** | [GitHub](https://github.com/TheHexenjagd/galleon_mc_audiosubs_remover)

> 💡 **Tip**: Usa la función "Verificar condiciones de subtítulos" antes de procesar una colección grande para identificar anomalías.

> ⚡ **Performance**: El procesamiento es extremadamente rápido porque no hay recodificación. Un archivo de 4GB puede procesarse en menos de 30 segundos.
