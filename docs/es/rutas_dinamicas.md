# Constructor de Rutas Dinámicas de Salida

<p align="right">
  <a href="../en/dynamic_paths.md">English</a> | <b>Español</b>
</p>

Cuando procesas grandes lotes de archivos de vídeo en Video Workstation (VW), la organización manual de los archivos resultantes puede tornarse tediosa. Para solucionar esto, VW cuenta con un **Constructor de Rutas Dinámicas**, que analiza el archivo y genera carpetas de salida estructuradas basándose en las propiedades y metadatos específicos de cada vídeo.

---

## Concepto de Subcarpetas Dinámicas
En el panel de **Opciones de Procesamiento** de la ventana principal, debajo de la ruta de salida, encontrarás la opción **"2. Subcarpeta: Crear"**.

* Si está desactivada, los vídeos procesados se guardarán directamente en la carpeta de salida seleccionada.
* Si está activa, VW creará una subcarpeta específica para cada vídeo basada en un patrón de texto personalizable, y colocará el archivo final dentro de ella.

---

## Marcadores y Variables Disponibles (Placeholders)
Puedes construir tu patrón de ruta utilizando las siguientes variables encerradas entre llaves `{}`. Al procesar cada archivo, VW reemplazará cada marcador con la información real extraída por FFprobe:

| Marcador | Propiedad a la que hace Referencia | Ejemplo de Salida |
|---|---|---|
| **`{name}`** | Nombre base del archivo original (sin extensión) | `Pelicula_2026` |
| **`{folder}`** | Nombre de la carpeta contenedora del archivo original | `Temporada 01` |
| **`{label}`** | Etiqueta de la combinación de pistas generada | `SPA_subENG_hardsub` |
| **`{audio_langs}`**| Idiomas de las pistas de audio seleccionadas | `SPA_ENG` |
| **`{sub_langs}`** | Idiomas de las pistas de subtítulos seleccionadas | `ENG` |
| **`{codec_v}`** | Códec del flujo de vídeo original | `h264` o `hevc` |
| **`{codec_a}`** | Códec del primer flujo de audio seleccionado | `aac`, `ac3` o `dts` |
| **`{resolution}`** | Resolución clasificada del archivo original | `1080p`, `2160p` o `720p` |

---

## El Diálogo del Constructor
Al pulsar el botón **"Configurar"** al lado de la casilla de Subcarpeta, se abrirá la ventana interactiva del constructor:

1. **Botones de Marcadores**: En la parte superior verás botones planos con etiquetas como `[Nombre]`, `[Directorio Padre]`, `[Resolución]`, etc. Al hacer clic en cualquiera de ellos, se insertará automáticamente el marcador correspondiente en el campo de texto (p. ej., hace clic en `[Resolución]` e inserta `{resolution}`).
2. **Vista Previa en Tiempo Real**: Debajo del cuadro de texto se muestra una simulación de cómo quedaría estructurada la ruta en base a valores de ejemplo, actualizándose al instante mientras escribes.
3. **Gestor de Presets**:
   * Si tienes un patrón de ruta que utilizas con frecuencia (p. ej., `{folder}/{resolution}/{codec_v}`), puedes escribirlo, pulsar **"Guardar preset"** y asignarle un nombre descriptivo.
   * La próxima vez que uses el programa, podrás seleccionarlo directamente de la lista desplegable de Presets en el constructor o en la ventana principal.

---

## Ejemplos Prácticos de Patrones de Ruta

### Ejemplo A: Organizar por Resolución y Códec de Vídeo
* **Patrón**: `{resolution}/{codec_v}`
* **Ruta Resultante**: `C:/Output/1080p/h264/Video_Procesado.mp4`
* *Ideal para separar contenido UHD de HD en carpetas distintas.*

### Ejemplo B: Mantener Estructura de Series y Versiones
* **Patrón**: `{folder}/{name}/{label}`
* **Ruta Resultante**: `C:/Output/Temporada 01/Episodio 01/SPA_subENG/Episodio 01_SPA_subENG.mp4`
* *Ideal para cuando generas múltiples versiones de audio/subtítulo de un mismo capítulo y deseas que cada versión quede en su propio subdirectorio ordenado.*

### Ejemplo C: Archivos Ordenados por Idioma de Audio
* **Patrón**: `Audios_{audio_langs}`
* **Ruta Resultante**: `C:/Output/Audios_SPA_ENG/Pelicula.mp4`
