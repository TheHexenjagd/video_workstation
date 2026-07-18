# 🎬 VPT Studio (Video Processing Toolkit) - v1.0.0

**VPT Studio** es una suite de escritorio desarrollada en Python y Tkinter orientada a la optimización de flujos de trabajo de procesamiento de vídeo. Automatiza tareas de multiplexado (remux), incrustado de subtítulos (hardcode), renombrado masivo y mantenimiento general de metadatos de archivos multimedia.

Este proyecto fusiona y mejora significativamente las funcionalidades de las herramientas:
* [hardcodetool](https://github.com/TheHexenjagd/hardcodetool) (Codificación por hardware de subtítulos)
* [audioselector](https://github.com/TheHexenjagd/audioselector) (Multiplexación y filtrado inteligente de pistas)

---

## 🚀 Funcionalidades Principales

VPT Studio cuenta con módulos dedicados y herramientas integradas para cubrir todas tus necesidades de post-procesamiento. Haz clic en los enlaces a continuación para ver guías y detalles de cada característica:

### 📦 [1. Multiplexado (Remux) y Versiones](docs/remux_selector.md)
Genera múltiples versiones de forma limpia (sin recodificar vídeo) a partir de las pistas de audio y subtítulos disponibles en tus archivos fuente.
* **Verificación de condiciones**: Analiza estadísticamente las pistas internas del contenedor para asegurar la disponibilidad de idiomas seleccionados.
* **Selector dinámico de pistas**: Interfaz dedicada para seleccionar múltiples combinaciones deseadas por archivo o lote.
* **Hardsub integrado directo**: Si seleccionas exactamente **una (1) pista de audio** y **un (1) subtítulo** en la combinación de la versión, se habilitará la opción de realizar el incrustado de subtítulos (`hardsub`) directamente desde este módulo en un solo clic, sin tener que recurrir al módulo independiente de Hardcode.
* 📖 [Leer documentación detallada sobre Remux y Selector](docs/remux_selector.md).

### ⚡ [2. Hardcode acelerado por GPU](docs/hardcode_gpu.md)
Incrusta subtítulos en el vídeo de forma permanente utilizando códecs acelerados por GPU.
* **Aceleración NVIDIA NVENC**: Codificación ultra rápida a través del códec `h264_nvenc`.
* **Aceleración Intel QSV**: Soporte para hardware Intel Quick Sync Video (`h264_qsv`).
* **Aceleración AMD AMF**: Soporte para hardware AMD Advanced Media Framework (`h264_amf`).
* **Decodificación por Hardware**: Opción de usar D3D11VA o DXVA2 para acelerar la lectura del archivo de vídeo.
* **Perfiles de velocidad/calidad (Presets)**: Perfiles personalizables para optimizar el rendimiento y la calidad visual de salida.
* 📖 [Leer documentación detallada sobre Hardcode y GPU](docs/hardcode_gpu.md).

### 🧹 [3. Mantenimiento de Archivos In-Place](docs/mantenimiento_metadata.md)
Herramientas rápidas para modificar directamente los contenedores de los archivos multimedia originales cargados en la cola:
* **Limpieza de metadatos**: Remueve etiquetas globales innecesarias, títulos no deseados y tags de codificadores en todos los streams del archivo.
* **Eliminar subtítulos**: Descarta por completo las pistas de subtítulos internos en un solo paso manteniendo intactos los flujos de audio y vídeo originales.
* 📖 [Leer documentación detallada sobre Mantenimiento](docs/mantenimiento_metadata.md).

### 🏷️ [4. Renombrador Masivo por Lotes](docs/renombrador.md)
* **Constructor de nombres**: Renombra todos los archivos de la cola principal utilizando comodines como `{num}` y `{name}`.
* **Búsqueda y Reemplazo por Regex**: Soporte avanzado para expresiones regulares (Regex) que permite limpiar etiquetas, corchetes, o extraer números de episodios específicos.
* **Presets de renombrado**: Guarda tus fórmulas personalizadas de renombrado masivo y reutilízalas cuando las necesites.
* 📖 [Leer documentación detallada sobre el Renombrador](docs/renombrador.md).

### ⚙️ [5. Constructor de Rutas Dinámicas de Salida](docs/rutas_dinamicas.md)
* **Organización automatizada**: Crea carpetas de salida inteligentes en base a metadatos extraídos de los vídeos procesados.
* **Marcadores dinámicos**: Utiliza marcadores como `{resolution}`, `{codec_v}`, `{codec_a}`, `{audio_langs}`, `{sub_langs}`, `{folder}` y `{name}` en tus rutas de salida.
* **Presets de constructor**: Sistema intuitivo de botones y presets interactivos para simplificar el diseño de la estructura de carpetas.
* 📖 [Leer documentación detallada sobre Rutas Dinámicas](docs/rutas_dinamicas.md).

---

## 🛑 Cancelación Inmediata e Inteligente

La aplicación cuenta con una rutina de detención de tareas por subprocesos no bloqueante (`subprocess.Popen` redireccionado de forma segura). Al hacer clic en **"Cancelar todo"**, se finaliza de forma **instantánea** cualquier instancia activa de FFmpeg/FFprobe corriendo en segundo plano, liberando de inmediato el procesador y la tarjeta gráfica del sistema sin demoras ni bloqueos de interfaz.

---

## 🛠️ Requisitos del Sistema

1. **Python 3.12** o superior.
2. **FFmpeg y FFprobe**: La aplicación los utiliza internamente para las operaciones de codificación y análisis de streams. Puedes configurar sus rutas en la interfaz gráfica (`Configuración -> Cambiar ruta...`).

---

## ⚙️ Parámetros de Configuración

Al abrir por primera vez la aplicación, se genera automáticamente un archivo de configuración en `%APPDATA%/Galleon/VPT/vpt_config.ini` con las siguientes opciones estándar:
* **ffmpeg**: `%APPDATA%/Galleon/bin/ffmpeg.exe`
* **ffprobe**: `%APPDATA%/Galleon/bin/ffprobe.exe`
* **buscar_recursivo**: `True` (Carga recursiva de carpetas)
* **crear_subcarpeta**: `False` (Exportación en la misma carpeta o ruta directa)
* **gpu_acel**: `"nvidia"` (Elige codificador por hardware: `"nvidia"`, `"intel"` o `"amd"`)
* **decod_hw**: `"Software"` (Elige decodificación: `"Software"`, `"d3d11va"` o `"dxva2"`)
* **preset**: `"medium"`
* **sufijo_idiomas**: `True` (Si está activo, añade el sufijo de idioma como `_SPA` o `_hardcoded` al archivo. Si está desactivado, conserva el nombre original).

---

## 👤 Desarrollador

* **Autor**: [TheHexenjagd](https://github.com/TheHexenjagd)
