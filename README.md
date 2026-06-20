# VPT Studio (Video Processing Toolkit)

VPT Studio es una suite de escritorio desarrollada en Python y Tkinter orientada a la optimización de flujos de trabajo de procesamiento de vídeo. Automatiza tareas de multiplexado (remux), incrustado de subtítulos (hardcode), y mantenimiento general de metadatos de archivos multimedia.

Este proyecto fusiona y mejora significativamente las funcionalidades de las herramientas:
* [hardcodetool](https://github.com/TheHexenjagd/hardcodetool) (Codificación por hardware de subtítulos)
* [audioselector](https://github.com/TheHexenjagd/audioselector) (Multiplexación y filtrado inteligente de pistas)

---

## 🚀 Funcionalidades Principales

### 1. Versiones Audio/Sub (Multiplexado)
Genera múltiples versiones de forma limpia (sin recodificar vídeo) a partir de las pistas de audio y subtítulos disponibles en tus archivos fuente.
* **Verificación de condiciones**: Analiza estadísticamente las pistas internas del contenedor para asegurar la disponibilidad de idiomas seleccionados.
* **Selector dinámico de pistas**: Interfaz dedicada para seleccionar múltiples combinaciones deseadas por archivo o lote.
* **Hardsub integrado directo**: Si seleccionas exactamente **una (1) pista de audio** y **un (1) subtítulo** en la combinación de la versión, se habilitará la opción de realizar el incrustado de subtítulos (`hardsub`) directamente desde este módulo en un solo clic, sin tener que recurrir al módulo independiente de Hardcode.

### 2. Hardcode (Codificación por Hardware)
Incrusta subtítulos en el vídeo de forma permanente utilizando códecs acelerados por GPU.
* **Aceleración NVIDIA NVENC**: Codificación ultra rápida a través del códec `h264_nvenc`.
* **Aceleración Intel QSV**: Soporte para hardware Intel Quick Sync Video (`h264_qsv`).
* **Aceleración AMD AMF**: Soporte para hardware AMD Advanced Media Framework (`h264_amf`).
* **Decodificación por Hardware**: Opción de usar D3D11VA o DXVA2 para acelerar la lectura del archivo de vídeo.
* **Preseteado de calidad**: Perfiles de velocidad y calidad personalizables para optimizar el renderizado según el hardware disponible.

### 3. Mantenimiento
* **Limpieza de metadatos**: Remueve metadatos innecesarios o no deseados de los flujos del archivo.
* **Verificación de streams**: Comprueba la integridad estructural de las pistas de vídeo.

---

## 🛑 Cancelación Inmediata e Inteligente
La aplicación cuenta con una rutina de detención de tareas por subprocesos no bloqueante (`subprocess.Popen` redireccionado a `/dev/null` para evitar interrupciones de búfer). Al hacer clic en **"Cancelar todo"**, se finaliza de forma **instantánea** cualquier instancia activa de FFmpeg/FFprobe corriendo en segundo plano, liberando de inmediato el procesador y la tarjeta gráfica del sistema sin demoras.

---

## 🛠️ Requisitos del Sistema
1. **Python 3.12** o superior.
2. **FFmpeg y FFprobe**: La aplicación los utiliza internamente para las operaciones de codificación y análisis de streams. Puedes configurar sus rutas en la interfaz gráfica.

---

## ⚙️ Parámetros de Configuración
Al abrir por primera vez la aplicación, se genera automáticamente un archivo de configuración en `%APPDATA%/Galleon/VPT/vpt_config.ini` con las siguientes opciones:
* **ffmpeg**: `%APPDATA%/Galleon/bin/ffmpeg.exe`
* **ffprobe**: `%APPDATA%/Galleon/bin/ffprobe.exe`
* **buscar_recursivo**: `True` (Carga recursiva de carpetas)
* **backup_original**: `True` (Crea una copia de respaldo antes de procesar)
* **crear_subcarpeta**: `False` (Exportación en la misma carpeta o ruta directa)
* **gpu_acel**: `"nvidia"` (Elige codificador por hardware: `"nvidia"`, `"intel"` o `"amd"`)
* **decod_hw**: `"Software"` (Elige decodificación: `"Software"`, `"d3d11va"` o `"dxva2"`)
* **usar_nvidia**: `True` (Mantenido por compatibilidad con herramientas antiguas)
* **preset**: `"medium"`
* **sufijo_idiomas**: `True` (Si está activo, añade el sufijo de idioma como `_SPA` o `_hardcoded` al archivo. Si está desactivado, conserva el nombre original del archivo intacto).

---

## 💻 Interfaz Gráfica
VPT Studio cuenta con una interfaz de usuario limpia e intuitiva:
* **Pestañas personalizadas estáticas**: Alternancia instantánea entre módulos mediante un diseño plano tipo "Pills" con indicador inferior azul. Su tamaño de contenedor se mantiene fijo y no altera la distribución de la ventana al navegar.
* **Checkbuttons sin sombras**: El selector de combinaciones y el árbol de pistas heredan el color nativo del tema de ventana de forma transparente y uniforme.
* **Constructor de Rutas Dinámicas (⚙️)**: Herramienta visual interactiva para personalizar los nombres de las carpetas de salida en función de marcadores dinámicos.
* **Consola de Actividad**: Visor en tiempo real de los procesos en ejecución y registros de eventos.

---

## 👤 Desarrollador
* **Autor**: [TheHexenjagd](https://github.com/TheHexenjagd)
