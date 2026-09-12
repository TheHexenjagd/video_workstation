# Hardcode y Aceleración por Hardware (GPU)

<p align="right">
  <a href="../en/gpu_hardcode.md">English</a> | <b>Español</b>
</p>

El módulo de **Hardcode** de Video Workstation (VW) permite incrustar permanentemente pistas de subtítulos en el flujo de vídeo principal (proceso comúnmente llamado *burn-in* o *hardsub*). Para evitar que este proceso consuma excesivos recursos del procesador (CPU) y demore demasiado, la suite cuenta con soporte completo de codificación y decodificación acelerada por hardware a través de tu tarjeta gráfica (GPU).

---

## Codificadores Acelerados por Hardware (GPU)
VW detecta y soporta tres tecnologías principales de codificación por hardware basadas en el fabricante de tu tarjeta gráfica:

### 1. NVIDIA NVENC (`h264_nvenc`)
* **Hardware**: Tarjetas gráficas NVIDIA GeForce / Quadro / Tesla.
* **Características**: Excelente velocidad de renderizado y eficiencia de codificación con muy bajo impacto en el procesador.
* **Códec utilizado**: `h264_nvenc` para salida compatible en formato H.264.

### 2. Intel Quick Sync Video (`h264_qsv`)
* **Hardware**: Procesadores Intel con gráficos integrados (Intel HD/UHD Graphics) o tarjetas discretas Intel Arc.
* **Características**: Excelente rendimiento de codificación integrado directamente en la CPU Intel.
* **Códec utilizado**: `h264_qsv`.

### 3. AMD Advanced Media Framework (`h264_amf`)
* **Hardware**: Tarjetas gráficas AMD Radeon / Radeon Pro.
* **Características**: Soporte dedicado para codificación acelerada en tarjetas de arquitectura AMD.
* **Códec utilizado**: `h264_amf`.

> [!NOTE]
> Al iniciar la aplicación, VW ejecuta subprocesos de prueba rápidos en segundo plano (`_iniciar_deteccion_gpus`) para comprobar la disponibilidad real de cada codificador en tu sistema. Si no dispones de hardware compatible con alguna tecnología, la opción correspondiente se mostrará como **(No disponible)** en la interfaz de usuario para evitar fallos de ejecución.

---

## Decodificación por Hardware
Además de acelerar la escritura del nuevo vídeo (codificación), también puedes acelerar la lectura y procesamiento del vídeo original (decodificación). VW ofrece tres modos de decodificación:

* **Software**: Decodifica el vídeo utilizando la CPU. Es la opción más compatible y segura si experimentas artefactos visuales en el vídeo procesado.
* **D3D11VA**: Decodificación acelerada por hardware a través de Direct3D 11 Video Acceleration. Recomendado para sistemas modernos con Windows 10/11.
* **DXVA2**: Decodificación acelerada por hardware a través de DirectX Video Acceleration 2. Ampliamente compatible con sistemas Windows anteriores y hardware antiguo.

---

## Perfiles de Rendimiento (Presets)
Cada codificador de hardware ofrece diferentes "presets" que permiten equilibrar la velocidad del renderizado frente a la calidad final del archivo generado. 

A continuación se detalla la oferta de perfiles disponibles en el programa:

### Presets de NVIDIA (NVENC)
| Preset | Nombre Técnico | Descripción | Velocidad | Calidad |
|---|---|---|---|---|
| **Lossless** | `lossless` | Codificación sin pérdida (archivos muy grandes) | ⚡☆☆ | ★★★★★ |
| **HQ** | `hq` | Prioriza la calidad visual | ⚡☆☆ | ★★★★☆ |
| **Slow (HQ)** | `slow` | Mayor compresión a costa de tiempo de procesamiento | ⚡☆☆ | ★★★★☆ |
| **BD** | `bd` | Perfil compatible con especificación Blu-ray | ⚡☆☆ | ★★★★☆ |
| **Default** | `default` | Balance estándar entre velocidad y calidad | ⚡⚡☆ | ★★★☆ |
| **Medium** | `medium` | Calidad intermedia estándar | ⚡⚡☆ | ★★★☆ |
| **LLHQ** | `llhq` | Baja latencia con enfoque en calidad | ⚡⚡☆ | ★★★☆ |
| **Fast** | `fast` | Codificación rápida, compresión estándar | ⚡⚡⚡ | ★★☆☆ |
| **LL** | `ll` | Ajuste de baja latencia | ⚡⚡⚡ | ★★☆☆ |
| **LLHP** | `llhp` | Baja latencia con enfoque en rendimiento | ⚡⚡⚡ | ★★☆☆ |
| **HP** | `hp` | Prioriza la máxima velocidad de procesamiento | ⚡⚡⚡⚡ | ★★☆☆ |

### Presets de Intel (QSV)
| Preset | Nombre Técnico | Descripción | Velocidad | Calidad |
|---|---|---|---|---|
| **Very Slow** | `veryslow` | Máxima calidad visual | ⚡☆☆ | ★★★★★ |
| **Slow** | `slow` | Alta calidad visual | ⚡☆☆ | ★★★★☆ |
| **Medium** | `medium` | Calidad balanceada con velocidad intermedia | ⚡⚡☆ | ★★★☆ |
| **Fast** | `fast` | Ajuste rápido y eficiente | ⚡⚡⚡ | ★★★☆ |
| **Faster** | `faster` | Prioriza la velocidad de exportación | ⚡⚡⚡ | ★★☆☆ |
| **Very Fast** | `veryfast` | Máxima velocidad posible | ⚡⚡⚡⚡ | ★★☆☆ |

### Presets de AMD (AMF)
| Preset | Nombre Técnico | Descripción | Velocidad | Calidad |
|---|---|---|---|---|
| **Quality** | `quality` | Prioriza la calidad de salida | ⚡☆☆ | ★★★★★ |
| **Balanced** | `balanced` | Punto intermedio entre calidad y velocidad | ⚡⚡☆ | ★★★☆ |
| **Speed** | `speed` | Prioriza la velocidad de renderizado | ⚡⚡⚡⚡ | ★★☆☆ |

---

## Advertencia de HDR (Alto Rango Dinámico)
Si intentas incrustar subtítulos en un vídeo codificado con metadatos HDR (como HDR10 o Dolby Vision) y el programa lo detecta durante el análisis previo, mostrará una advertencia:
> *El vídeo original tiene rango dinámico HDR. Si decides generar versiones con subtítulos incrustados (hardsub), los colores podrían verse lavados.*

Esto ocurre porque la codificación rápida H.264 por hardware no realiza de forma nativa el mapeo de tonos (*tonemapping*) a SDR, lo cual es importante tener en cuenta antes de iniciar la renderización.
