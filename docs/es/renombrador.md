# Renombrador de Archivos por Lotes

<p align="right">
  <a href="../en/batch_renamer.md">English</a> | <b>Español</b>
</p>

El **Renombrador Masivo** integrado en Video Workstation (VW) te permite reorganizar y homogeneizar de forma rápida los nombres de los archivos cargados en la cola principal mediante patrones estructurados y filtros avanzados de texto.

---

## Interfaz del Renombrador
Para acceder al renombrador, debes tener al menos un archivo en la cola principal de la ventana de VW y pulsar el botón **"Renombrar"** en la sección de *Mantenimiento*. Se abrirá una ventana dedicada dividida en:

1. **Panel Izquierdo (Configuración)**: Donde defines las reglas de renombrado, numeración y reemplazo de texto.
2. **Panel Derecho (Vista Previa)**: Una tabla interactiva de dos columnas que muestra el **Nombre Original** del archivo y el **Nuevo Nombre** calculado en tiempo real. Esto permite verificar los cambios antes de aplicarlos.

---

## 1. Configuración del Patrón de Nombre
El renombrador utiliza dos comodines o variables clave para construir el nombre base:

* **`{name}`**: El nombre original del archivo (sin la extensión ni la ruta).
* **`{num}`**: Un contador incremental secuencial.

### Opciones de la Secuencia (`{num}`)
* **Inicio**: Define el número por el cual empezará el contador (p. ej., si tu lista comienza en el episodio 13, pon `13`).
* **Dígitos**: El relleno de ceros a la izquierda (padding) para mantener la uniformidad de los nombres en los exploradores de archivos:
  * Con dígitos = `2`: `01`, `02`, `03`...
  * Con dígitos = `3`: `001`, `002`, `003`...

---

## 2. Búsqueda y Reemplazo con Expresiones Regulares (Regex)
Además del patrón básico, puedes aplicar operaciones de limpieza en el nombre original `{name}` antes de procesarlo. Si marcas la opción **"Usar Regex"**, puedes usar expresiones regulares para extraer o limpiar texto.

### Ejemplos Prácticos de Expresiones Regulares

#### A. Eliminar corchetes de grupos de fansub o tags (p. ej., `[Fansub] Video.mp4` ➡️ `Video.mp4`)
* **Buscar**: `\[.*?\]`
* **Reemplazar**: *(dejar vacío)*

#### B. Extraer número de capítulo de un texto largo (p. ej., `Capitulo 156 - El Regreso` ➡️ `156 El Regreso.mp4`)
* **Buscar**: `Capitulo (\d+) - (.*)`
* **Reemplazar**: `\1 \2` (donde `\1` es el grupo del número y `\2` es el título del capítulo)

#### C. Limpiar múltiples espacios en blanco consecutivos
* **Buscar**: `\s+`
* **Reemplazar**: ` ` (un espacio simple)

---

## 3. Presets de Renombrado
Para ahorrar tiempo, la ventana incluye una lista desplegable con **Ajustes Predefinidos** que configuran automáticamente el patrón y las expresiones regulares para los casos de uso más comunes:

1. **Numeración Simple**: Renombra los archivos solo con números correlativos (`01.mp4`, `02.mp4`...).
2. **Numeración + Nombre**: Agrega el número secuencial seguido del nombre original del archivo (`01 - Nombre.mp4`...).
3. **Extraer Capítulo**: Diseñado para reescribir títulos de anime o series limpiando la palabra "Capítulo".
4. **Extraer Número de Episodio**: Extrae números de temporada/episodio de formatos como `01x03` o `s01e01`.
5. **Limpiar Etiquetas**: Remueve corchetes `[...]` y paréntesis `(...)` del nombre original.

### Guardar tus propios Ajustes
Puedes guardar tus configuraciones complejas para uso futuro:
* Configura tus patrones y Regex en el formulario.
* Haz clic en **"Guardar preset"**, asígnale un nombre descriptivo y pulsa guardar. Se almacenará en tu configuración de VW.
* Si deseas eliminar un preset guardado, selecciónalo y presiona **"Eliminar"**.
