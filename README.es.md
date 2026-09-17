# Video Workstation (VW)

<p align="center">
  <b>Estación de trabajo de escritorio en Python para multiplexado por lotes, incrustado de subtítulos acelerado por hardware y mantenimiento integral de metadatos de vídeo.</b>
</p>

<p align="center">
  <a href="README.md">English</a> | <b>Español</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/Plataforma-Windows-0078D6?style=flat&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/GUI-Tkinter-blueviolet" alt="Tkinter">
  <img src="https://img.shields.io/badge/Multimedia-FFmpeg-007808?style=flat&logo=ffmpeg&logoColor=white" alt="FFmpeg">
  <img src="https://img.shields.io/badge/Licencia-MIT-green?style=flat" alt="Licencia MIT">
</p>

---

## Descripción General

El procesamiento por lotes de colecciones multimedia tradicionalmente requiere la formulación de scripts complejos en línea de comandos o el uso de editores de vídeo sobredimensionados que consumen recursos excesivos y conllevan el riesgo de recodificaciones no deseadas.

**Video Workstation (VW)** es una estación de trabajo de escritorio desarrollada en Python y Tkinter diseñada para optimizar y acelerar los flujos de trabajo de post-procesamiento de vídeo en lotes masivos. Centraliza y amplía de forma robusta las capacidades de multiplexación de flujos sin pérdida (remuxing), incrustado permanente de subtítulos acelerado por hardware (GPU), saneamiento masivo de etiquetas y metadatos, renombrado por expresiones regulares y organización inteligente de carpetas basada en propiedades multimedia.

Construida con énfasis en el rendimiento, la integridad absoluta de datos y la ergonomía del usuario, VW proporciona un centro de control visual intuitivo sobre FFmpeg y FFprobe sin requerir librerías de terceros en tiempo de ejecución.

---

## Características Principales

- **Multiplexado sin pérdida (Remux) y selector de versiones:** Extrae y ensambla múltiples pistas de audio y subtítulos sin recodificar el flujo de vídeo original, garantizando cero degradación de calidad visual a la velocidad física de transferencia del disco.
- **Incrustado de subtítulos acelerado por hardware (GPU Hardcode):** Integración profunda con pipelines de codificación por GPU (NVIDIA NVENC, Intel Quick Sync y AMD AMF) y aceleración de decodificación por hardware (D3D11VA, DXVA2) para renderizar subtítulos incrustados a máxima velocidad.
- **Mantenimiento y saneamiento de metadatos in-place:** Eliminación masiva de etiquetas de codificador, marcas de distribución y títulos en contenedores multimedia (`-map_metadata -1`), junto con el descarte rápido de pistas internas de subtítulos (`-sn`) sin recompresión.
- **Renombrador masivo por lotes con expresiones regulares:** Constructor de nombres con variables dinámicas (`{name}`, `{num}`), relleno numérico configurable y motor avanzado de búsqueda y sustitución regex para limpiar patrones complejos en bibliotecas de archivos.
- **Constructor de rutas dinámicas de salida:** Organización automatizada en subcarpetas basadas en metadatos técnicos inspeccionados vía FFprobe (`{resolution}`, `{codec_v}`, `{codec_a}`, `{audio_langs}`, `{sub_langs}`, `{folder}`, `{name}`).
- **Resolución inteligente de binarios:** Detección en cascada de `ffmpeg.exe` y `ffprobe.exe` en directorio local `tools/` (modo 100% portable), ruta de usuario `%APPDATA%/VideoWorkstation/tools/` o variable de entorno `PATH` del sistema.
- **Cero dependencias externas en tiempo de ejecución:** Construido íntegramente sobre la biblioteca estándar de Python (`tkinter`, `subprocess`, `threading`, `queue`, `json`, `configparser`, `pathlib`).

---

## Arquitectura y Aspectos Técnicos Destacados

- **Concurrencia multihilo no bloqueante:** El análisis de contenedores y los procesos intensivos de codificación de FFmpeg se delegan a hilos de trabajo independientes (`threading.Thread`), comunicándose con el hilo principal de la interfaz gráfica a través de colas seguras para subprocesos (`queue.Queue`), asegurando una respuesta fluida y sin bloqueos en la interfaz de usuario.
- **Control estricto de subprocesos y cancelación instantánea:** Implementa un control riguroso sobre instancias de `subprocess.Popen`. Al solicitar la cancelación de una tarea en cola, la aplicación finaliza de forma inmediata los procesos hijos de FFmpeg/FFprobe a nivel del sistema operativo, liberando al instante los recursos de la GPU y CPU sin dejar procesos huérfanos ni fugas de memoria.
- **Operaciones atómicas seguras en archivos (In-Place):** Las tareas destructivas que modifican archivos fuente operan bajo un patrón transaccional atómico: procesan en archivos temporales aislados, validan la terminación exitosa (`exit code 0`) y solo entonces realizan la sustitución atómica del archivo original. Cualquier fallo interrumpe la tarea y purga los temporales, preservando la integridad del archivo original intacto.
- **Sondeo dinámico de hardware:** Identifica en tiempo de ejecución la disponibilidad real de codificadores por hardware (`h264_nvenc`, `h264_qsv`, `h264_amf`) y adapta los controles de la interfaz gráfica a las capacidades de cómputo del equipo.
- **Persistencia desacoplada de configuración:** Gestión centralizada y atómica de preferencias de usuario en archivo INI (`vw_config.ini`) en el directorio de datos de la aplicación.
- **Empaquetado portable automatizado:** Incluye el script orquestador `dist/build.py`, `dist/build.bat` (Windows) y `dist/build.sh` (Linux / macOS), los cuales verifican el entorno, detectan entornos virtuales (`venv`), empaquetan con PyInstaller y generan un ejecutable final independiente.

---

## Documentación

Las guías detalladas para cada uno de los módulos de la aplicación se encuentran organizadas en español e inglés:

- **Multiplexado y Selector de Versiones:** [Español (docs/es/remux_selector.md)](docs/es/remux_selector.md) | [English (docs/en/remux_selector.md)](docs/en/remux_selector.md)
- **Incrustado por GPU (Hardcode):** [Español (docs/es/hardcode_gpu.md)](docs/es/hardcode_gpu.md) | [English (docs/en/gpu_hardcode.md)](docs/en/gpu_hardcode.md)
- **Mantenimiento de Metadatos:** [Español (docs/es/mantenimiento_metadata.md)](docs/es/mantenimiento_metadata.md) | [English (docs/en/metadata_maintenance.md)](docs/en/metadata_maintenance.md)
- **Renombrador por Lotes:** [Español (docs/es/renombrador.md)](docs/es/renombrador.md) | [English (docs/en/batch_renamer.md)](docs/en/batch_renamer.md)
- **Rutas Dinámicas de Salida:** [Español (docs/es/rutas_dinamicas.md)](docs/es/rutas_dinamicas.md) | [English (docs/en/dynamic_paths.md)](docs/en/dynamic_paths.md)

---

## Estructura del Proyecto

```text
video_workstation/
├── dist/
│   ├── build.bat                   # Generador automatizado para Windows
│   ├── build.sh                    # Generador automatizado para Linux y macOS
│   └── build.py                    # Script de compilación y empaquetado con PyInstaller
├── docs/
│   ├── en/
│   │   ├── batch_renamer.md        # Guía en inglés: Renombrador por lotes
│   │   ├── dynamic_paths.md        # Guía en inglés: Rutas dinámicas de salida
│   │   ├── gpu_hardcode.md         # Guía en inglés: Incrustado acelerado por GPU
│   │   ├── metadata_maintenance.md # Guía en inglés: Mantenimiento de metadatos
│   │   └── remux_selector.md       # Guía en inglés: Multiplexado y versiones
│   └── es/
│       ├── hardcode_gpu.md         # Guía en español: Incrustado acelerado por GPU
│       ├── mantenimiento_metadata.md # Guía en español: Mantenimiento de metadatos
│       ├── remux_selector.md       # Guía en español: Multiplexado y versiones
│       ├── renombrador.md          # Guía en español: Renombrador por lotes
│       └── rutas_dinamicas.md      # Guía en español: Rutas dinámicas de salida
├── tools/
│   └── README.txt                  # Instrucciones para binarios portables (ffmpeg/ffprobe)
├── vw.py                           # Punto de entrada e interfaz gráfica principal (Tkinter)
├── LICENSE                         # Términos de la licencia MIT
├── README.md                       # Documentación principal en inglés
└── README.es.md                    # Documentación en español
```

---

## Instalación y Ejecución

### Prerrequisitos

- **Sistema Operativo:** Windows 10 / 11 (64-bit).
- **Python:** 3.12 o superior instalado.
- **FFmpeg y FFprobe:** Necesarios para la inspección y procesamiento multimedia. Pueden proveerse de tres maneras:
  1. **Modo Portátil (Recomendado):** Descargar y ubicar `ffmpeg.exe` y `ffprobe.exe` en la carpeta local `tools/`.
  2. **Directorio de Usuario:** Ubicados en `%APPDATA%/VideoWorkstation/tools/`.
  3. **PATH del Sistema:** Detectados automáticamente si están instalados globalmente en Windows.

### Inicio Rápido (Ejecución desde código fuente)

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/TheHexenjagd/VW.git
   cd VW
   ```

2. (Opcional) Ubicar los binarios `ffmpeg.exe` y `ffprobe.exe` dentro del directorio `tools/`.

3. Iniciar la aplicación:
   ```bash
   python vw.py
   ```

---

## Generación del Ejecutable Portable

El proyecto incluye generadores automatizados para compilar un binario portable independiente (sin requerir instalación de Python en la máquina de destino):

- **En Windows:** Haz doble clic en `dist/build.bat` o ejecuta:
  ```cmd
  dist\build.bat
  ```
- **En Linux / macOS:** Ejecuta:
  ```bash
  chmod +x dist/build.sh
  ./dist/build.sh
  ```
- **O directamente mediante Python en cualquier plataforma:**
  ```bash
  python dist/build.py
  ```

El script verificará las herramientas de compilación, detectará el entorno virtual (`venv`) si existe, aplicará metadatos cuando corresponda (Windows), limpiará archivos temporales y generará el binario compilado en la carpeta `dist/`.

---

## Configuración

Las preferencias del usuario se persisten automáticamente en `%APPDATA%/VideoWorkstation/vw_config.ini`:

- **Rutas de binarios:** Almacenamiento y resolución de rutas de `ffmpeg.exe` y `ffprobe.exe`.
- **Aceleración por hardware:** Selección de codificador por GPU (`nvidia`, `intel`, `amd`) y decodificador por hardware (`Software`, `d3d11va`, `dxva2`).
- **Parámetros de procesamiento:** Fórmulas dinámicas de salida, reglas de sufijos de idioma, exploración recursiva y perfiles de calidad de codificación.

---

## Autores y Equipo de Desarrollo

Proyecto desarrollado y mantenido por:

<table align="center">
  <tr>
    <td align="center" width="260px">
      <a href="https://github.com/TheHexenjagd">
        <img src="https://github.com/TheHexenjagd.png" width="110px;" alt="Gabriel Giraldo Herrera"/><br />
        <sub><b>Gabriel Giraldo Herrera</b></sub>
      </a><br />
      <a href="https://github.com/TheHexenjagd"><code>@TheHexenjagd</code></a><br />
      <small>Co-Creador y Desarrollador</small>
    </td>
    <td align="center" width="260px">
      <a href="https://github.com/Gatozo">
        <img src="https://github.com/Gatozo.png" width="110px;" alt="Jorge Iván Nieto Triviño"/><br />
        <sub><b>Jorge Iván Nieto Triviño</b></sub>
      </a><br />
      <a href="https://github.com/Gatozo"><code>@Gatozo</code></a><br />
      <small>Co-Creador y Desarrollador</small>
    </td>
  </tr>
</table>

---

## Licencia

Este proyecto está bajo los términos de la **Licencia MIT** — consulta el archivo [LICENSE](LICENSE) para más detalles.
