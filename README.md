# VPT Studio (Video Processing Toolkit)

VPT Studio es una suite profesional de escritorio desarrollada en Python y Tkinter orientada a la optimización de flujos de trabajo de procesamiento de vídeo. Automatiza tareas de multiplexado (remux), incrustado de subtítulos (hardcode), y mantenimiento general de metadatos de archivos multimedia.

Este proyecto fusiona y mejora significativamente las funcionalidades de las herramientas:
* [hardcodetool](https://github.com/TheHexenjagd/hardcodetool) (Codificación por hardware de subtítulos)
* [audioselector](https://github.com/TheHexenjagd/audioselector) (Multiplexación y filtrado inteligente de pistas)

---

## 🚀 Funcionalidades Principales

### 1. Versiones Audio/Sub (Multiplexado)
Genera múltiples versiones de forma limpia (sin recodificar vídeo) a partir de las pistas de audio y subtítulos disponibles en tus archivos fuente.
* **Verificación de condiciones**: Analiza estadísticamente las pistas internas del contenedor para asegurar la disponibilidad de idiomas seleccionados.
* **Selector dinámico de pistas**: Interfaz dedicada para seleccionar múltiples combinaciones deseadas por archivo o lote.

### 2. Hardcode (Codificación por Hardware)
Incrusta subtítulos en el vídeo de forma permanente utilizando códecs acelerados por GPU.
* **Aceleración NVIDIA NVENC**: Codificación ultra rápida a través del códec `h264_nvenc`.
* **Aceleración Intel QSV**: Soporte para hardware Intel Quick Sync Video.
* **Preseteado de calidad**: Perfiles de velocidad y calidad personalizables para optimizar el renderizado según el hardware disponible.

### 3. Mantenimiento
* **Limpieza de metadatos**: Remueve metadatos innecesarios o no deseados de los flujos del archivo.
* **Verificación de streams**: Comprueba la integridad estructural de las pistas de vídeo.

---

## 🛠️ Requisitos del Sistema
1. **Python 3.12** o superior.
2. **FFmpeg y FFprobe**: La aplicación los utiliza internamente para las operaciones de codificación y análisis de streams. Puedes configurar sus rutas en la interfaz gráfica.

---

## ⚙️ Configuración Inicial
Al abrir por primera vez la aplicación, se genera automáticamente un archivo de configuración en `%APPDATA%/Galleon/VPT/vpt_config.ini` con los siguientes parámetros por defecto:
* **ffmpeg**: `%APPDATA%/Galleon/bin/ffmpeg.exe`
* **ffprobe**: `%APPDATA%/Galleon/bin/ffprobe.exe`
* **buscar_recursivo**: `True` (Carga recursiva de carpetas)
* **backup_original**: `True` (Crea una copia de respaldo antes de procesar)
* **crear_subcarpeta**: `False` (Exportación en la misma carpeta o ruta directa)
* **usar_nvidia**: `True` (Intenta usar codificación NVIDIA NVENC por defecto)
* **preset**: `"medium"`

---

## 💻 Interfaz Gráfica
VPT Studio cuenta con una interfaz moderna y premium con:
* **Pestañas personalizadas**: Alternancia fluida entre módulos (Versiones, Hardcode y Mantenimiento) mediante un diseño plano con indicador inferior azul.
* **Constructor de Rutas Dinámicas (⚙️)**: Herramienta visual interactiva para personalizar los nombres de las carpetas de salida en función de las pistas de audio, subtítulos y nombre del archivo utilizando marcadores dinámicos.
* **Cola de Videos**: Lista con carga múltiple e importación recursiva de directorios completos.
* **Consola de Actividad**: Visor en tiempo real de los procesos en ejecución y registros de FFmpeg.

---

## 👤 Desarrollador
* **Autor**: [TheHexenjagd](https://github.com/TheHexenjagd)
