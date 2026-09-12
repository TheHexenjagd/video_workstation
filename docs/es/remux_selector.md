# Multiplexado (Remux) y Selector de Versiones

<p align="right">
  <a href="../en/remux_selector.md">English</a> | <b>Español</b>
</p>

El módulo de **Multiplexado (Remux)** de Video Workstation (VW) está diseñado para procesar múltiples pistas de audio y subtítulos, permitiendo generar diferentes versiones de un archivo de vídeo de manera limpia, rápida y sin pérdida de calidad en la pista de vídeo principal.

---

## ¿Qué es el Remux?
El remuestreo o multiplexado (**remux**) es el proceso de copiar los flujos de datos existentes (vídeo, audio, subtítulos) de un contenedor (como `.mkv` o `.mp4`) e introducirlos en un nuevo contenedor con una selección específica de pistas. 

* **Sin Pérdida**: Dado que el vídeo no se recodifica, la calidad de la imagen original se mantiene al 100%.
* **Velocidad Ultra Rápida**: Al evitar la codificación de vídeo por CPU/GPU, la operación se completa en pocos segundos por archivo, limitada únicamente por la velocidad de lectura/escritura de tu unidad de almacenamiento.

---

## Selector Dinámico de Pistas y Versiones
Al iniciar el procesamiento de un vídeo o un lote, VW analiza el archivo fuente a través de **FFprobe** y presenta una interfaz visual interactiva que permite construir las versiones deseadas:

1. **Visualización de Pistas Disponibles**: 
   * **Pistas de Audio**: Muestra el título y el idioma de cada pista (p. ej., `Español (spa)`, `Inglés (eng)`).
   * **Pistas de Subtítulos**: Muestra las pistas de subtítulos internos detectados.
2. **Generación de Versiones**:
   * Selecciona las combinaciones de pistas de audio y subtítulos deseadas.
   * Haz clic en **"Agregar versión"** para registrar una nueva combinación en la lista de salida. Puedes añadir múltiples combinaciones para generar varias versiones a partir del mismo archivo de origen.
   * **Aplicar a todos**: Si procesas un lote de archivos con la misma estructura, puedes marcar la opción "Aplicar a todos" para usar las mismas combinaciones de idiomas en el resto del lote de forma automatizada.

---

## Validación y Pre-verificación de la Cola
Antes de procesar un lote de vídeos, puedes utilizar el botón **"Verificar cola"** para realizar un análisis de compatibilidad:

* **Análisis de Idiomas**: Comprueba si todos los archivos de la cola contienen los idiomas requeridos para las versiones seleccionadas.
* **Alertas Estadísticas**: Informa sobre archivos que carecen de pistas específicas y los clasifica.
* **Reporte de Compatibilidad**: Al finalizar el análisis, el programa abre una ventana detallada con estadísticas:
  * **Archivos Compatibles**: Listado de archivos listos para procesar sin problemas.
  * **Archivos Incompatibles**: Archivos a los que les faltan pistas. El programa te permite decidir si deseas reintentar, omitirlos de forma segura (moviéndolos a la pestaña de "Omitidos / Errores"), o forzar su procesamiento de todos modos.

---

## Hardsub Integrado Directo (Incrustado de Subtítulos)
Normalmente, incrustar subtítulos requiere pasar por un proceso completo de codificación en el módulo de Hardcode. Sin embargo, VW incluye una función híbrida sumamente útil:

* **Activación Automática**: Si en el selector de pistas marcas **exactamente una (1) pista de audio** y **exactamente una (1) pista de subtítulos**, se habilitará de forma automática el botón **"Hacer hardsub (Incrustar)"** en el selector.
* **Flujo Unificado**: Al activar esta opción, VW multiplexará el audio seleccionado e incrustará permanentemente la pista de subtítulos elegida en el vídeo en un solo paso, utilizando los parámetros de aceleración por hardware (GPU) configurados en el panel principal.
