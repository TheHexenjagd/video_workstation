# Herramientas de Mantenimiento

<p align="right">
  <a href="../en/metadata_maintenance.md">English</a> | <b>Español</b>
</p>

El módulo de **Mantenimiento** de Video Workstation (VW) agrupa utilidades rápidas diseñadas para modificar o depurar los archivos de vídeo originales de la cola. A diferencia de las funciones de multiplexado o hardcode, estas herramientas están pensadas para realizar modificaciones directamente en el contenedor del archivo de origen.

---

## 1. Eliminar Metadatos (Limpieza de Tags)
Los archivos multimedia (especialmente los contenedores `.mkv` y `.mp4`) a menudo contienen metadatos innecesarios incrustados por herramientas de codificación, como etiquetas globales, títulos del archivo, nombres del software de conversión, o información del codificador en cada pista individual.

### ¿Qué hace esta herramienta?
* **Limpieza Completa**: Elimina las etiquetas de metadatos globales y los metadatos específicos de cada stream (pistas de vídeo, audio y subtítulos) utilizando los comandos de FFmpeg:
  ```bash
  ffmpeg -i "archivo_origen" -map 0 -c copy -map_metadata -1 -map_metadata:s:v -1 -map_metadata:s:a -1 -map_metadata:s:s -1 "archivo_temp"
  ```
* **Sin Recodificación**: Todos los flujos de audio, vídeo y subtítulos se copian exactamente sin alteración (`-c copy`), lo que hace que la operación se realice a la máxima velocidad física del disco duro.
* **Resultado Limpio**: Tu archivo quedará libre de marcas, títulos de pista no deseados y descripciones de software.

---

## 2. Eliminar Subtítulos
Hay ocasiones en las que las pistas de subtítulos internas de un archivo están corruptas, son innecesarias o interfieren con los reproductores multimedia.

### ¿Qué hace esta herramienta?
* **Descarte de Subtítulos**: Procesa el archivo para conservar únicamente los flujos de vídeo y audio, omitiendo por completo cualquier pista de subtítulos que contenga el archivo de origen (`-sn` de FFmpeg):
  ```bash
  ffmpeg -i "archivo_origen" -map 0 -c copy -sn "archivo_temp"
  ```
* **Rápido e In-place**: Al igual que la limpieza de metadatos, no recodifica nada y se ejecuta instantáneamente.

---

## Seguridad en Modificaciones Directas (In-Place)
Dado que estas operaciones modifican los archivos originales de la lista principal, VW implementa varias medidas de seguridad automáticas:

1. **Procesamiento Temporal**: La herramienta nunca escribe directamente sobre el archivo que está leyendo. En su lugar, escribe el resultado en un archivo temporal (`.tmp` o con sufijo aleatorio) dentro de la misma carpeta.
2. **Reemplazo Seguro**: Una vez completado FFmpeg con éxito (`exit code 0`), el programa elimina el archivo original y renombra el temporal con el nombre del original.
3. **Manejo de Errores**: Si ocurre un fallo en FFmpeg o se cancela el proceso:
   * El archivo temporal creado se elimina automáticamente para no dejar basura.
   * El archivo original permanece intacto sin ninguna alteración.
   * El archivo que falló se retira de la "Cola principal" y se mueve a la pestaña de **"Omitidos / Errores"** junto con el log de error para que puedas inspeccionar qué causó la falla.
