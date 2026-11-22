"""FFprobe/FFmpeg execution, GPU detection, queue workers, and batch sanitization mixin."""

import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from video_workstation.config import TOOLS_DIR
from video_workstation.constants import (
    BITMAP_SUB_CODECS,
    INCOMPATIBLE_MP4_AUDIO_CODECS,
    STRIP_METADATA_ARGS,
)
from video_workstation.media.ffprobe import (
    find_track_by_identifier as encontrar_pista_por_identificador,
    get_track_identifier as obtener_identificador_pista,
    is_hdr_video as _video_es_hdr,
)
from video_workstation.media.presets import get_valid_preset as obtener_preset_valido
from video_workstation.media.subtitles import (
    ensure_external_subtitle_utf8 as asegurar_subtitulo_externo_utf8,
    find_external_subtitles as buscar_subtitulos_externos,
)
from video_workstation.ui.theme import get_theme
from video_workstation.utils.binaries import (
    get_binary_filename,
    resolve_binary_path,
)
from video_workstation.utils.downloader import download_ffmpeg_tools


def resolve_app_binary(binary_name):
    return resolve_binary_path(binary_name, TOOLS_DIR)


class MediaProcessorMixin:
    """Mixin encapsulating FFprobe inspection, GPU probing, and FFmpeg batch execution."""

    def _ffprobe_info(self, filepath):
        filepath = os.path.abspath(os.path.normpath(filepath))
        if hasattr(self, "ffprobe_cache") and filepath in self.ffprobe_cache:
            return self.ffprobe_cache[filepath]

        if len(filepath) > 260 and not filepath.startswith("\\\\?\\"):
            filepath = "\\\\?\\" + filepath

        cmd = [self.ffprobe_path, "-v", "error", "-print_format", "json", "-show_streams", filepath]
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
        if result.returncode != 0:
            self._log_message(f"Error ffprobe: {result.stderr[:220]}")
            return None

        try:
            data = json.loads(result.stdout)
            if "streams" not in data:
                return None
            if getattr(self, "var_buscar_subtitulos_externos", None) is None or self.var_buscar_subtitulos_externos.get():
                self._attach_external_subtitles(filepath, data)
            if hasattr(self, "ffprobe_cache"):
                self.ffprobe_cache[filepath] = data
            return data
        except json.JSONDecodeError:
            return None

    def _attach_external_subtitles(self, filepath, data):
        if not data or "streams" not in data:
            return
        data["streams"] = [s for s in data["streams"] if not s.get("is_external")]
        ext_subs = buscar_subtitulos_externos(filepath)
        if not ext_subs:
            return
        max_idx = max([s.get("index", 0) for s in data["streams"]], default=0)
        for i, sub in enumerate(ext_subs, start=1):
            stream_idx = max_idx + 100 + i
            ext_stream = {
                "index": stream_idx,
                "codec_type": "subtitle",
                "codec_name": "subrip",
                "is_external": True,
                "external_path": sub["path"],
                "tags": {
                    "language": sub["lang_code"],
                    "title": f"[EXT] {sub['lang_label']}",
                },
                "disposition": {
                    "default": 0,
                    "forced": 1 if "forzado" in sub["lang_label"].lower() else 0,
                }
            }
            data["streams"].append(ext_stream)

    def _invalidate_file_cache(self, filepath):
        if not hasattr(self, "ffprobe_cache"):
            return
        filepath_norm = os.path.abspath(os.path.normpath(filepath))
        if filepath_norm in self.ffprobe_cache:
            del self.ffprobe_cache[filepath_norm]

        path_obj = Path(filepath_norm)
        ext = path_obj.suffix
        if ext != ext.lower():
            lower_norm = os.path.abspath(os.path.normpath(path_obj.with_suffix(ext.lower())))
            if lower_norm in self.ffprobe_cache:
                del self.ffprobe_cache[lower_norm]

    def _get_language_signature(self, info):
        if not info or "streams" not in info:
            return ((), ())
        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
        audio_langs = tuple((s.get("tags") or {}).get("language", "und").lower() for s in audio_streams)
        sub_langs = tuple((s.get("tags") or {}).get("language", "und").lower() for s in subtitle_streams)
        return (audio_langs, sub_langs)

    def _format_language_summary(self, langs, max_items=5):
        if not langs:
            return "NINGUNO"
        unicos = list(dict.fromkeys(l.upper() for l in langs if l))
        if not unicos:
            return "NINGUNO"
        if len(unicos) <= max_items:
            return ", ".join(unicos)
        visibles = ", ".join(unicos[:max_items])
        restantes = len(unicos) - max_items
        return f"{visibles} (+{restantes} más)"

    def _find_compatible_signature(self, firma):
        if hasattr(self, "combinaciones_por_grupo") and firma in self.combinaciones_por_grupo:
            return firma
        return None

    def _check_ffmpeg_on_startup(self):
        ffmpeg_bin = get_binary_filename("ffmpeg")
        ffprobe_bin = get_binary_filename("ffprobe")

        if not (self.ffmpeg_path and os.path.exists(self.ffmpeg_path)):
            self.ffmpeg_path = resolve_app_binary(ffmpeg_bin)
        if not (self.ffprobe_path and os.path.exists(self.ffprobe_path)):
            self.ffprobe_path = resolve_app_binary(ffprobe_bin)

        if os.path.exists(self.ffmpeg_path) and os.path.exists(self.ffprobe_path):
            self._update_config()
            return

        self._show_ffmpeg_setup_dialog(ffmpeg_bin, ffprobe_bin)

    def _show_ffmpeg_setup_dialog(self, ffmpeg_bin, ffprobe_bin):
        t = get_theme(self.theme_var.get())
        dlg = tk.Toplevel(self.root)
        dlg.title("Configuración inicial - Video Workstation")
        dlg.geometry("580x400")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=t["bg_app"])
        dlg._vw_themed = True

        dlg.update_idletasks()
        px = self.root.winfo_x() + max(0, (self.root.winfo_width() - 580) // 2)
        py = self.root.winfo_y() + max(0, (self.root.winfo_height() - 400) // 2)
        dlg.geometry(f"+{px}+{py}")

        # Header
        hdr = tk.Frame(dlg, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        hdr.pack(fill=tk.X, padx=18, pady=(14, 10))
        hdr_in = tk.Frame(hdr, bg=t["bg_surface"])
        hdr_in.pack(fill=tk.X, padx=14, pady=10)
        tk.Label(hdr_in, text="VW", font=("Segoe UI", 11, "bold"), bg=t["accent"], fg="#FFFFFF", padx=8, pady=2).pack(side=tk.LEFT)
        hdr_txt = tk.Frame(hdr_in, bg=t["bg_surface"])
        hdr_txt.pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(hdr_txt, text="FFmpeg y FFprobe requeridos", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W)
        tk.Label(hdr_txt, text="No se detectaron los binarios en el sistema ni en las carpetas de herramientas.", font=("Segoe UI", 8), bg=t["bg_surface"], fg=t["fg_muted"]).pack(anchor=tk.W)

        # Card principal
        card = tk.Frame(dlg, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        card.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 14))

        body = tk.Frame(card, bg=t["bg_surface"])
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        lbl_intro = tk.Label(
            body,
            text="Puedes descargar e instalar los binarios oficiales automáticamente o colocarlos de forma manual.",
            font=("Segoe UI", 9),
            bg=t["bg_surface"],
            fg=t["fg_secondary"],
            wraplength=510,
            justify=tk.LEFT,
        )
        lbl_intro.pack(anchor=tk.W, pady=(0, 12))

        # Bloque de progreso (oculto hasta iniciar descarga)
        prog_box = tk.Frame(body, bg=t["bg_subtle"], highlightthickness=1, highlightbackground=t["border"])
        lbl_status = tk.Label(prog_box, text="Preparando descarga...", font=("Segoe UI", 9, "bold"), bg=t["bg_subtle"], fg=t["fg_primary"])
        lbl_status.pack(anchor=tk.W, padx=12, pady=(10, 4))
        pbar = ttk.Progressbar(prog_box, style="Modern.Horizontal.TProgressbar", mode="indeterminate")
        pbar.pack(fill=tk.X, padx=12, pady=4)
        lbl_bytes = tk.Label(prog_box, text="Conectando...", font=("Segoe UI", 8), bg=t["bg_subtle"], fg=t["fg_muted"])
        lbl_bytes.pack(anchor=tk.W, padx=12, pady=(2, 10))

        # Bloque de rutas manuales (visible por defecto o al rechazar descarga)
        manual_box = tk.Frame(body, bg=t["bg_subtle"], highlightthickness=1, highlightbackground=t["border"])
        manual_box.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        tk.Label(
            manual_box,
            text=f"Instalación manual (coloca '{ffmpeg_bin}' y '{ffprobe_bin}' en):",
            font=("Segoe UI", 8, "bold"),
            bg=t["bg_subtle"],
            fg=t["fg_primary"],
        ).pack(anchor=tk.W, padx=12, pady=(10, 6))

        rutas_txt = f"Carpeta de herramientas:\n  {TOOLS_DIR}"
        if os.name != "nt":
            rutas_txt += "\n\nO instala ffmpeg a nivel de sistema (apt / dnf / pacman / brew)."

        tk.Label(
            manual_box,
            text=rutas_txt,
            font=("Consolas", 8),
            bg=t["bg_subtle"],
            fg=t["fg_secondary"],
            justify=tk.LEFT,
            anchor=tk.W,
        ).pack(anchor=tk.W, padx=12, pady=(0, 10))

        def _abrir_carpeta_tools():
            os.makedirs(TOOLS_DIR, exist_ok=True)
            try:
                if os.name == "nt":
                    os.startfile(TOOLS_DIR)
                elif os.uname().sysname == "Darwin":
                    subprocess.Popen(["open", TOOLS_DIR])
                else:
                    subprocess.Popen(["xdg-open", TOOLS_DIR])
            except Exception:
                pass

        # Botonera inferior
        btns = tk.Frame(body, bg=t["bg_surface"])
        btns.pack(fill=tk.X, side=tk.BOTTOM)

        def on_status(txt):
            if dlg.winfo_exists():
                self.root.after(0, lambda s=txt: lbl_status.config(text=s) if dlg.winfo_exists() else None)

        def on_progress(downloaded, total):
            if not dlg.winfo_exists():
                return
            mb_dl = downloaded / (1024 * 1024)
            if total > 0:
                pct = min(100.0, (downloaded / total) * 100)
                mb_tot = total / (1024 * 1024)

                def _upd():
                    if not dlg.winfo_exists():
                        return
                    if str(pbar.cget("mode")) != "determinate":
                        pbar.stop()
                        pbar.config(mode="determinate", maximum=100)
                    pbar["value"] = pct
                    lbl_bytes.config(text=f"{mb_dl:.1f} MB / {mb_tot:.1f} MB ({pct:.0f}%)")

                self.root.after(0, _upd)
            else:
                self.root.after(0, lambda: lbl_bytes.config(text=f"{mb_dl:.1f} MB descargados...") if dlg.winfo_exists() else None)

        def _iniciar_descarga():
            btn_dl.config(state=tk.DISABLED)
            btn_open.config(state=tk.DISABLED)
            btn_manual.config(state=tk.DISABLED)
            dlg.protocol("WM_DELETE_WINDOW", lambda: None)
            manual_box.pack_forget()
            prog_box.pack(fill=tk.X, pady=(0, 12))
            pbar.start(12)

            def worker():
                try:
                    ff_path, fp_path = download_ffmpeg_tools(TOOLS_DIR, status_cb=on_status, progress_cb=on_progress)

                    def _ok():
                        if dlg.winfo_exists():
                            dlg.destroy()
                        self.ffmpeg_path = ff_path
                        self.ffprobe_path = fp_path
                        self._update_config()
                        self._start_gpu_detection()
                        messagebox.showinfo("Descarga completada", f"FFmpeg y FFprobe instalados correctamente en:\n{TOOLS_DIR}", parent=self.root)

                    self.root.after(0, _ok)
                except Exception as exc:
                    def _err():
                        if not dlg.winfo_exists():
                            return
                        pbar.stop()
                        prog_box.pack_forget()
                        manual_box.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
                        btn_dl.config(state=tk.NORMAL)
                        btn_open.config(state=tk.NORMAL)
                        btn_manual.config(state=tk.NORMAL)
                        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
                        messagebox.showerror("Error al descargar", f"No se pudo completar la descarga:\n{exc}", parent=dlg)

                    self.root.after(0, _err)

            threading.Thread(target=worker, daemon=True).start()

        btn_dl = tk.Button(btns, text="Descargar automáticamente", command=_iniciar_descarga, bg=t["btn_primary"], fg="#FFFFFF", padx=14, pady=5, font=("Segoe UI", 9, "bold"), disabled_bg=t["btn_disabled_bg"], disabled_fg=t["btn_disabled_fg"])
        btn_dl.pack(side=tk.LEFT, padx=(0, 8))

        btn_open = tk.Button(btns, text="Abrir carpeta", command=_abrir_carpeta_tools, bg=t["btn_secondary_bg"], fg=t["btn_secondary_fg"], padx=12, pady=5, font=("Segoe UI", 9, "bold"), disabled_bg=t["btn_disabled_bg"], disabled_fg=t["btn_disabled_fg"])
        btn_open.pack(side=tk.LEFT)

        btn_manual = tk.Button(btns, text="Lo haré manualmente", command=dlg.destroy, bg=t["btn_secondary_bg"], fg=t["btn_secondary_fg"], padx=12, pady=5, font=("Segoe UI", 9), disabled_bg=t["btn_disabled_bg"], disabled_fg=t["btn_disabled_fg"])
        btn_manual.pack(side=tk.RIGHT)

    def _on_gpu_change(self):
        preset_actual = self.preset_var.get()
        nuevo = obtener_preset_valido(preset_actual, self.gpu_acel_var.get())
        if nuevo != preset_actual:
            self.preset_var.set(nuevo)

    def _is_nvidia_available(self):
        return self._check_encoder("h264_nvenc")

    def _check_encoder(self, encoder):
        if not os.path.exists(self.ffmpeg_path):
            return False, "FFmpeg no encontrado"

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            encoders_proc = subprocess.run(
                [self.ffmpeg_path, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=5
            )
            if encoders_proc.returncode != 0 or encoder not in encoders_proc.stdout:
                return False, "No soportado por FFmpeg"

            test_proc = subprocess.run(
                [
                    self.ffmpeg_path,
                    "-hide_banner",
                    "-f",
                    "lavfi",
                    "-i",
                    "nullsrc=s=256x256:d=1",
                    "-c:v",
                    encoder,
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=5
            )
            if test_proc.returncode != 0:
                err_msg = test_proc.stderr.strip().split("\n")[-1] if test_proc.stderr else "Driver o GPU no disponible"
                return False, err_msg
            return True, "Disponible"
        except Exception as exc:
            return False, f"Error: {exc}"

    def _start_gpu_detection(self):
        self._log_message("Iniciando detección de hardware gráfico...")
        threading.Thread(target=self._detect_gpus_worker, daemon=True).start()

    def _detect_gpus_worker(self):
        nv_ok, nv_msg = self._check_encoder("h264_nvenc")
        intel_ok, intel_msg = self._check_encoder("h264_qsv")
        amd_ok, amd_msg = self._check_encoder("h264_amf")

        self.gpus_status = {
            "nvidia": (nv_ok, nv_msg),
            "intel": (intel_ok, intel_msg),
            "amd": (amd_ok, amd_msg)
        }

        self._log_message(f"Detección GPU - NVIDIA NVENC: {'OK' if nv_ok else 'No disponible (' + nv_msg + ')'}")
        self._log_message(f"Detección GPU - Intel QSV: {'OK' if intel_ok else 'No disponible (' + intel_msg + ')'}")
        self._log_message(f"Detección GPU - AMD AMF: {'OK' if amd_ok else 'No disponible (' + amd_msg + ')'}")

        self.root.after(0, self._update_gpu_selector_ui)

    def _update_gpu_selector_ui(self):
        values = []
        available_keys = []
        self.gpu_availability = {}
        for gpu_key, display_name in [("nvidia", "NVIDIA (NVENC)"), ("intel", "Intel (QSV)"), ("amd", "AMD (AMF)")]:
            is_ok = self.gpus_status.get(gpu_key, (False, ""))[0]
            self.gpu_availability[gpu_key] = is_ok
            if is_ok:
                values.append(display_name)
                available_keys.append(gpu_key)
                self.gpu_map_display_to_val[display_name] = gpu_key

        if not values:
            self.cb_gpu.config(values=["Sin GPU disponible"], state="disabled")
            self.cb_gpu.set("Sin GPU disponible")
            return

        self.cb_gpu.config(values=values, state="readonly")
        if self.gpu_acel_var.get() not in available_keys:
            self.gpu_acel_var.set(available_keys[0])
        self._sync_gpu_combobox()

    def _sync_gpu_combobox(self):
        current_val = self.gpu_acel_var.get()
        for lbl in self.cb_gpu["values"]:
            if self.gpu_map_display_to_val.get(lbl) == current_val:
                self.cb_gpu.set(lbl)
                break

    def _on_gpu_selected(self, event=None):
        selected_lbl = self.cb_gpu.get()
        gpu_key = self.gpu_map_display_to_val.get(selected_lbl)

        is_ok = self.gpu_availability.get(gpu_key, True)
        if not is_ok:
            status = self.gpus_status.get(gpu_key, (False, "No disponible"))
            messagebox.showwarning(
                "Codificador no disponible",
                f"El codificador seleccionado ({selected_lbl}) no está disponible o no se pudo inicializar en su sistema.\nDetalle: {status[1]}\n\nSe restablecerá la selección anterior.",
                parent=self.root
            )
            self._sync_gpu_combobox()
            return

        self.gpu_acel_var.set(gpu_key)
        self._on_gpu_change()

    def _get_combinations_to_build(self, info, filename):
        if self.cancelar_procesamiento:
            return None

        firma = self._get_language_signature(info)

        signature_match = self._find_compatible_signature(firma)
        if signature_match:
            self._log_message(f"  -> Aplicando configuración previamente guardada para el grupo de idiomas.")
            config_grupo = self.combinaciones_por_grupo[signature_match]
            combos = []
            for c in config_grupo:
                if self.cancelar_procesamiento:
                    return None
                audio_indices = [encontrar_pista_por_identificador(info["streams"], ident, "audio") for ident in c["audio_identifiers"]]
                sub_indices = [encontrar_pista_por_identificador(info["streams"], ident, "subtitle") for ident in c["sub_identifiers"] if ident != "NINGUNO"]

                audio_indices = [x for x in audio_indices if x is not None]
                sub_indices = [x for x in sub_indices if x is not None]

                combos.append({
                    "audio_indices": audio_indices,
                    "sub_indices": sub_indices,
                    "audio_identifiers": c["audio_identifiers"],
                    "sub_identifiers": c["sub_identifiers"],
                    "label": c["label"],
                    "hardsub": c["hardsub"]
                })
            if combos:
                return combos

        if self.cancelar_procesamiento:
            return None

        subgrupo_num = self.subgrupos.get(firma, 1)
        audio_langs_str = self._format_language_summary(firma[0])
        sub_langs_str = self._format_language_summary(firma[1])
        subgrupo_label = f"Subgrupo {subgrupo_num} (Audio: {audio_langs_str} | Subs: {sub_langs_str})"

        self._log_message(f"  -> Abriendo selección de versiones para el {subgrupo_label}...")

        q = queue.Queue()
        self.msg_queue.put(("SELECTOR_COMBINACIONES", info, filename, subgrupo_label, q))
        try:
            r = q.get(timeout=300)
        except queue.Empty:
            return None

        if self.cancelar_procesamiento or not r.get("ok") or not r.get("combinaciones"):
            return None

        if r.get("aplicar_todos"):
            if hasattr(self, "combinaciones_por_grupo"):
                self.combinaciones_por_grupo[firma] = [
                    {
                        "audio_identifiers": c.get("audio_identifiers", []),
                        "sub_identifiers": c.get("sub_identifiers", []),
                        "label": c["label"],
                        "hardsub": c.get("hardsub", False),
                    }
                    for c in r["combinaciones"]
                ]

        return r["combinaciones"]

    def _build_combinations(self, input_file, output_dir, info, combinaciones, errores):
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
        video_stem = Path(input_file).stem

        ok = 0
        fail = 0
        limpiar_meta = bool(self.var_eliminar_metadatos.get())
        meta_args = list(STRIP_METADATA_ARGS) if limpiar_meta else []

        for i, combo in enumerate(combinaciones, 1):
            if self.cancelar_procesamiento:
                break
            audio_indices = combo.get("audio_indices", [])
            sub_indices = combo.get("sub_indices", [])
            label = combo.get("label", "VERSION")

            out_dir = Path(output_dir)
            if self.var_subcarpeta.get():
                patron = self._resolve_subfolder_pattern(input_file, info, label, audio_indices, sub_indices)
                out_dir = out_dir / Path(patron)

            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / f"{video_stem}.mp4"
            self._invalidate_file_cache(output_path)

            usar_hardsub = bool(combo.get("hardsub"))
            if usar_hardsub:
                if _video_es_hdr(info):
                    self._log_message(f"  -> Aviso: Hardsub desactivado en '{label}' (video HDR; se hará remux sin pérdida para proteger el color).")
                    usar_hardsub = False
                elif sub_indices:
                    sub_obj = next((st for st in subtitle_streams if st.get("index") == sub_indices[0]), None)
                    if sub_obj and (sub_obj.get("codec_name") or "").lower() in BITMAP_SUB_CODECS:
                        self._log_message(f"  -> Aviso: Hardsub desactivado en '{label}' (subtítulo bitmap no compatible con incrustación).")
                        usar_hardsub = False

            if usar_hardsub:
                gpu = self.gpu_acel_var.get()
                is_ok = self.gpu_availability.get(gpu, True)
                if not is_ok:
                    status = self.gpus_status.get(gpu, (False, "No disponible"))
                    err_msg = f"El codificador {gpu.upper()} no está disponible. Detalle: {status[1]}"
                    self._log_message(f"Error: {err_msg}. Saltando hardsub.")
                    self._record_activity("error", os.path.basename(input_file), f"Hardsub ({label})", err_msg, item_key=f"combo:{output_path}")
                    errores.append((input_file, f"Versión '{label}': {err_msg}"))
                    fail += 1
                    continue

                audio_idx = audio_indices[0] if audio_indices else None
                sub_idx = sub_indices[0] if sub_indices else None
                temp_subtitle_path = None
                temp_utf8_sub_path = None

                try:
                    if sub_idx is not None:
                        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False, encoding="utf-8")
                        temp_subtitle_path = tf.name
                        tf.close()

                        sub_stream_obj = next((st for st in info["streams"] if st.get("index") == sub_idx), None)
                        if sub_stream_obj and sub_stream_obj.get("is_external"):
                            ext_file = sub_stream_obj.get("external_path")
                            actual_sub_path, temp_utf8_sub_path = asegurar_subtitulo_externo_utf8(ext_file)
                            extract = [self.ffmpeg_path, "-i", actual_sub_path, "-y", temp_subtitle_path]
                        else:
                            extract = [self.ffmpeg_path, "-i", input_file, "-map", f"0:{sub_idx}", "-y", temp_subtitle_path]

                        res = self._run_subprocess_cancellable(extract)
                        if res.returncode != 0:
                            err_detail = ""
                            if hasattr(res, "stderr") and res.stderr:
                                lines_err = [l.strip() for l in res.stderr.splitlines() if l.strip()]
                                if lines_err:
                                    err_detail = f" Detalle: {' '.join(lines_err[-2:])}"
                            err_msg = f"Fallo al extraer/procesar subtítulo de la versión '{label}'.{err_detail}"
                            self._log_message(err_msg)
                            self._record_activity("error", os.path.basename(input_file), f"Hardsub ({label})", err_msg, item_key=f"combo:{output_path}")
                            errores.append((input_file, f"Versión '{label}': {err_msg}"))
                            fail += 1
                            continue

                        esc = temp_subtitle_path.replace("\\", "/").replace(":", "\\:")
                        video_filter = f"ass='{esc}',format=yuv420p"
                    else:
                        video_filter = "format=yuv420p"

                    audio_codec = None
                    for s in info["streams"]:
                        if s.get("codec_type") == "audio" and s.get("index") == audio_idx:
                            audio_codec = s.get("codec_name")
                            break
                    audio_codec_lower = str(audio_codec).lower() if audio_codec else ""
                    audio_settings = ["-c:a", "aac", "-b:a", "320k"] if audio_codec_lower in INCOMPATIBLE_MP4_AUDIO_CODECS else ["-c:a", "copy"]

                    preset = obtener_preset_valido(self.preset_var.get(), self.gpu_acel_var.get())

                    decod_val = self.decod_hw_var.get().lower()
                    hwaccel_opts = []
                    if decod_val in ("d3d11va", "dxva2") and sub_idx is None:
                        hwaccel_opts = ["-hwaccel", decod_val]

                    color_flags = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]

                    if gpu == "nvidia":
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_nvenc", "-preset", preset,
                            "-profile:v", "high", "-rc", "vbr", "-cq", "23",
                            "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *color_flags,
                            *audio_settings, *meta_args, "-movflags", "+faststart", "-y", str(output_path)
                        ]
                    elif gpu == "intel":
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_qsv", "-preset", preset,
                            "-global_quality", "23",
                            "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *color_flags,
                            *audio_settings, *meta_args, "-movflags", "+faststart", "-y", str(output_path)
                        ]
                    else:
                        cmd = [
                            self.ffmpeg_path, *hwaccel_opts, "-i", input_file,
                            "-map", "0:v:0", "-map", f"0:{audio_idx}",
                            "-vf", video_filter,
                            "-c:v", "h264_amf", "-quality", preset,
                            "-rc", "vbr_peak", "-b:v", "5M", "-maxrate", "8M", "-bufsize", "10M",
                            *color_flags,
                            *audio_settings, *meta_args, "-movflags", "+faststart", "-y", str(output_path)
                        ]

                    self._record_activity("procesando", os.path.basename(input_file), f"Hardsub ({label})", "Incrustando subtítulos...", item_key=f"combo:{output_path}")
                    result = self._run_subprocess_cancellable(cmd)
                    if result.returncode == 0:
                        ok += 1
                        aud_langs = []
                        for idx in audio_indices:
                            s = next((st for st in info["streams"] if st.get("index") == idx), None)
                            if s:
                                lang = s.get("tags", {}).get("language", "und")
                                title = s.get("tags", {}).get("title", "")
                                codec = s.get("codec_name", "")
                                aud_langs.append(f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})")

                        sub_langs = []
                        sub_list = [sub_idx] if sub_idx is not None else []
                        for idx in sub_list:
                            s = next((st for st in info["streams"] if st.get("index") == idx), None)
                            if s:
                                lang = s.get("tags", {}).get("language", "und")
                                title = s.get("tags", {}).get("title", "")
                                codec = s.get("codec_name", "")
                                sub_langs.append(f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})")

                        ruta_completa = os.path.abspath(output_path)
                        audios_info = ", ".join(aud_langs) if aud_langs else "Ninguno"
                        subs_info = ", ".join(sub_langs) if sub_langs else "Ninguno"
                        carpeta_salida = output_path.parent.name or str(output_path.parent)
                        meta_txt = "Sin metadatos" if limpiar_meta else "Con metadatos"
                        self._record_activity(
                            "exito",
                            os.path.basename(input_file),
                            f"Hardsub ({label})",
                            f"Carpeta: {carpeta_salida}/ | {meta_txt}",
                            item_key=f"combo:{output_path}",
                            log_extra={
                                "Salida": ruta_completa,
                                "Audios": audios_info,
                                "Subtítulos": subs_info,
                                "Metadatos": "Eliminados" if limpiar_meta else "Conservados",
                            },
                        )
                    else:
                        err_detail = ""
                        if hasattr(result, "stderr") and result.stderr:
                            lines_err = [l.strip() for l in result.stderr.splitlines() if l.strip()]
                            if lines_err:
                                err_detail = f" Detalle: {' '.join(lines_err[-2:])}"
                        err_msg = f"Error de FFmpeg al codificar la versión hardsub (código de salida: {result.returncode}).{err_detail}"
                        self._log_message(err_msg)
                        self._record_activity("error", os.path.basename(input_file), f"Hardsub ({label})", err_msg, item_key=f"combo:{output_path}")
                        errores.append((input_file, f"Versión '{label}': {err_msg}"))
                        fail += 1
                finally:
                    if temp_subtitle_path and os.path.exists(temp_subtitle_path):
                        try:
                            os.unlink(temp_subtitle_path)
                        except Exception:
                            pass
                    if temp_utf8_sub_path and os.path.exists(temp_utf8_sub_path):
                        try:
                            os.unlink(temp_utf8_sub_path)
                        except Exception:
                            pass
            else:
                sub_incluir = []
                excluidos = 0
                for idx in sub_indices:
                    s = next((st for st in subtitle_streams if st["index"] == idx), None)
                    if s and s.get("codec_name", "").lower() in BITMAP_SUB_CODECS:
                        excluidos += 1
                    else:
                        sub_incluir.append(idx)

                if excluidos:
                    self._log_message(f"Advertencia: {excluidos} subtítulos bitmap/no texto excluidos")

                video_streams = [s for s in info["streams"] if s.get("codec_type") == "video"]
                main_video_streams = [s for s in video_streams if not s.get("disposition", {}).get("attached_pic")]
                if not main_video_streams:
                    main_video_streams = video_streams

                ext_inputs = {}
                temp_utf8_files = []
                next_in_idx = 1
                for idx in sub_incluir:
                    s = next((st for st in subtitle_streams if st["index"] == idx), None)
                    if s and s.get("is_external"):
                        ext_path = s["external_path"]
                        if ext_path not in ext_inputs:
                            actual_path, temp_path = asegurar_subtitulo_externo_utf8(ext_path)
                            if temp_path:
                                temp_utf8_files.append(temp_path)
                            ext_inputs[ext_path] = (next_in_idx, actual_path)
                            next_in_idx += 1

                try:
                    cmd = [self.ffmpeg_path, "-i", input_file]
                    for ext_path, (in_idx, actual_path) in sorted(ext_inputs.items(), key=lambda x: x[1][0]):
                        cmd.extend(["-i", actual_path])

                    for s in main_video_streams:
                        cmd.extend(["-map", f"0:{s['index']}"])
                        if s.get("codec_name", "").lower() in ("hevc", "h265"):
                            cmd.extend(["-tag:v", "hvc1"])

                    cmd.extend(["-c:v", "copy"])

                    for idx_pos, idx in enumerate(audio_indices):
                        cmd.extend(["-map", f"0:{idx}"])
                        s = next((st for st in info["streams"] if st.get("index") == idx), None)
                        acodec = s.get("codec_name", "").lower() if s else ""
                        if acodec in INCOMPATIBLE_MP4_AUDIO_CODECS:
                            cmd.extend([f"-c:a:{idx_pos}", "aac", f"-b:a:{idx_pos}", "320k"])
                        else:
                            cmd.extend([f"-c:a:{idx_pos}", "copy"])

                    if not audio_indices:
                        cmd.extend(["-c:a", "copy"])

                    for out_sub_pos, idx in enumerate(sub_incluir):
                        s = next((st for st in subtitle_streams if st["index"] == idx), None)
                        if s and s.get("is_external"):
                            in_idx = ext_inputs[s["external_path"]][0]
                            cmd.extend(["-map", f"{in_idx}:0"])
                        else:
                            cmd.extend(["-map", f"0:{idx}"])
                        if s and not limpiar_meta:
                            tags_s = s.get("tags") or {}
                            lang_s = tags_s.get("language")
                            if lang_s:
                                cmd.extend([f"-metadata:s:s:{out_sub_pos}", f"language={lang_s}"])

                    if sub_incluir:
                        cmd.extend(["-c:s", "mov_text"])

                    cmd.extend([*meta_args, "-movflags", "+faststart", "-y", str(output_path)])

                    self._record_activity("procesando", os.path.basename(input_file), f"Remux ({label})", "Multiplexando pistas...", item_key=f"combo:{output_path}")
                    result = self._run_subprocess_cancellable(cmd)

                    if result.returncode != 0 and sub_incluir:
                        self._log_message("  -> Advertencia: Falló multiplexado de subtítulos en MP4. Reintentando remux sin subtítulos...")
                        cmd_fallback = [self.ffmpeg_path, "-i", input_file]
                        for s in main_video_streams:
                            cmd_fallback.extend(["-map", f"0:{s['index']}"])
                            if s.get("codec_name", "").lower() in ("hevc", "h265"):
                                cmd_fallback.extend(["-tag:v", "hvc1"])
                        cmd_fallback.extend(["-c:v", "copy"])
                        for idx_pos, idx in enumerate(audio_indices):
                            cmd_fallback.extend(["-map", f"0:{idx}"])
                            s = next((st for st in info["streams"] if st.get("index") == idx), None)
                            acodec = s.get("codec_name", "").lower() if s else ""
                            if acodec in INCOMPATIBLE_MP4_AUDIO_CODECS:
                                cmd_fallback.extend([f"-c:a:{idx_pos}", "aac", f"-b:a:{idx_pos}", "320k"])
                            else:
                                cmd_fallback.extend([f"-c:a:{idx_pos}", "copy"])
                        if not audio_indices:
                            cmd_fallback.extend(["-c:a", "copy"])
                        cmd_fallback.extend(["-sn", *meta_args, "-movflags", "+faststart", "-y", str(output_path)])
                        result = self._run_subprocess_cancellable(cmd_fallback)
                        if result.returncode == 0:
                            sub_incluir = []
                finally:
                    for tf in temp_utf8_files:
                        if tf and os.path.exists(tf):
                            try:
                                os.unlink(tf)
                            except Exception:
                                pass

                if result.returncode == 0:
                    ok += 1
                    aud_langs = []
                    for idx in audio_indices:
                        s = next((st for st in info["streams"] if st.get("index") == idx), None)
                        if s:
                            lang = s.get("tags", {}).get("language", "und")
                            title = s.get("tags", {}).get("title", "")
                            codec = s.get("codec_name", "")
                            aud_langs.append(f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})")

                    sub_langs = []
                    for idx in sub_incluir:
                        s = next((st for st in info["streams"] if st.get("index") == idx), None)
                        if s:
                            lang = s.get("tags", {}).get("language", "und")
                            title = s.get("tags", {}).get("title", "")
                            codec = s.get("codec_name", "")
                            sub_langs.append(f"{lang} ({title} - {codec})" if title else f"{lang} ({codec})")

                    ruta_completa = os.path.abspath(output_path)
                    audios_info = ", ".join(aud_langs) if aud_langs else "Ninguno"
                    subs_info = ", ".join(sub_langs) if sub_langs else "Ninguno"
                    carpeta_salida = output_path.parent.name or str(output_path.parent)
                    meta_txt = "Sin metadatos" if limpiar_meta else "Con metadatos"
                    self._record_activity(
                        "exito",
                        os.path.basename(input_file),
                        f"Remux ({label})",
                        f"Carpeta: {carpeta_salida}/ | {meta_txt}",
                        item_key=f"combo:{output_path}",
                        log_extra={
                            "Salida": ruta_completa,
                            "Audios": audios_info,
                            "Subtítulos": subs_info,
                            "Metadatos": "Eliminados" if limpiar_meta else "Conservados",
                        },
                    )
                else:
                    err_detail = ""
                    if hasattr(result, "stderr") and result.stderr:
                        lines = [l.strip() for l in result.stderr.splitlines() if l.strip()]
                        if lines:
                            err_detail = f" Detalle: {' '.join(lines[-2:])}"
                    err_msg = f"Error de FFmpeg al copiar/remuxear la versión (código de salida: {result.returncode}).{err_detail}"
                    self._log_message(err_msg)
                    self._record_activity("error", os.path.basename(input_file), f"Remux ({label})", err_msg, item_key=f"combo:{output_path}")
                    errores.append((input_file, f"Versión '{label}': {err_msg}"))
                    fail += 1

        return ok, fail

    def _strip_tracks_processing(self, archivo, output_dir, errores):
        if self.cancelar_procesamiento:
            return False

        info = self._ffprobe_info(archivo)
        if info is None:
            err_msg = "No se pudo leer streams con ffprobe."
            self._log_message(err_msg)
            errores.append((archivo, err_msg))
            return False

        if self.cancelar_procesamiento:
            return False

        v = sum(1 for s in info["streams"] if s.get("codec_type") == "video")
        if v < 1:
            err_msg = "El archivo no contiene ninguna pista de video."
            self._log_message(err_msg)
            errores.append((archivo, err_msg))
            return False

        combinaciones = self._get_combinations_to_build(info, archivo)
        if self.cancelar_procesamiento or combinaciones is None:
            if not self.cancelar_procesamiento:
                err_msg = "Se canceló la selección de combinaciones."
                self._log_message(err_msg)
                errores.append((archivo, err_msg))
            return False

        return self._build_combinations(archivo, output_dir, info, combinaciones, errores)

    def _clear_subgroups(self):
        if hasattr(self, "subgrupos"):
            self.subgrupos.clear()
        else:
            self.subgrupos = {}
        if hasattr(self, "combinaciones_por_grupo"):
            self.combinaciones_por_grupo.clear()
        else:
            self.combinaciones_por_grupo = {}
        self.combinaciones_a_aplicar = {"combinaciones": [], "aplicar_a_todos": False}
        self.pistas_config = {"audio_tag": None, "subtitle_tag": None, "aplicar_a_todos": False}

    def _get_subgroup_map(self, archivos):
        subgrupos_dict = {}
        subgrupo_counter = 1
        for archivo in archivos:
            info = self._ffprobe_info(archivo)
            if not info:
                continue
            firma = self._get_language_signature(info)
            if firma not in subgrupos_dict:
                subgrupos_dict[firma] = {
                    "firma": firma,
                    "num": subgrupo_counter,
                    "archivos": [archivo],
                    "sample_archivo": archivo,
                    "sample_info": info,
                }
                subgrupo_counter += 1
            else:
                subgrupos_dict[firma]["archivos"].append(archivo)
        return list(subgrupos_dict.values())

    def _preconfigure_queue_subgroups(self, archivos, output_dir=None, forzar_reconfiguracion=False):
        subgrupos_list = self._get_subgroup_map(archivos)
        if not subgrupos_list:
            self._clear_subgroups()
            return True

        if not hasattr(self, "combinaciones_por_grupo") or forzar_reconfiguracion:
            self.combinaciones_por_grupo = {}

        if not hasattr(self, "subgrupos") or forzar_reconfiguracion:
            self.subgrupos = {}
        for sg in subgrupos_list:
            self.subgrupos[sg["firma"]] = sg["num"]

        pendientes = [sg for sg in subgrupos_list if sg["firma"] not in self.combinaciones_por_grupo]
        if not pendientes:
            return True

        total_sg = len(subgrupos_list)

        for sg in pendientes:
            firma = sg["firma"]
            sample_info = sg["sample_info"]
            sample_archivo = sg["sample_archivo"]

            audio_streams = [s for s in sample_info.get("streams", []) if s.get("codec_type") == "audio"]
            subtitle_streams = [s for s in sample_info.get("streams", []) if s.get("codec_type") == "subtitle"]

            if not audio_streams and not subtitle_streams:
                self.combinaciones_por_grupo[firma] = []
                continue

            cant_archivos = len(sg["archivos"])
            txt_archivos = f"{cant_archivos} archivo" if cant_archivos == 1 else f"{cant_archivos} archivos"
            audio_langs_str = self._format_language_summary(firma[0])
            sub_langs_str = self._format_language_summary(firma[1])
            subgrupo_label = f"Subgrupo {sg['num']} de {total_sg} ({txt_archivos}) | Audio: {audio_langs_str} | Subs: {sub_langs_str}"

            while True:
                r = self._show_combination_selector(
                    sample_info,
                    sample_archivo,
                    subgrupo_label=subgrupo_label,
                    modo_previo=True
                )
                if r.get("ok") and r.get("combinaciones"):
                    self.combinaciones_por_grupo[firma] = [
                        {
                            "audio_identifiers": c.get("audio_identifiers", []),
                            "sub_identifiers": c.get("sub_identifiers", []),
                            "label": c["label"],
                            "hardsub": c.get("hardsub", False),
                        }
                        for c in r["combinaciones"]
                    ]
                    break
                else:
                    if output_dir is not None:
                        ans = messagebox.askyesno(
                            "Cancelar procesamiento",
                            f"Has cancelado la configuración del {subgrupo_label}.\n\n¿Deseas cancelar el inicio del procesamiento de toda la cola?",
                            parent=self.root
                        )
                        if ans:
                            self._clear_subgroups()
                            return False
                        else:
                            ans_omitir = messagebox.askyesno(
                                "Omitir subgrupo",
                                f"¿Deseas omitir los {txt_archivos} correspondientes a este subgrupo y continuar con los demás?\n\n(Si eliges 'No', volverás a abrir la configuración de este subgrupo)",
                                parent=self.root
                            )
                            if ans_omitir:
                                self._move_to_skipped(sg["archivos"])
                                break
                            else:
                                continue
                    else:
                        self._clear_subgroups()
                        return False

        return True

    def _process_queue_worker(self, archivos, output_dir):
        self.procesando = True
        self.cancelar_procesamiento = False
        self.combinaciones_a_aplicar = {"combinaciones": [], "aplicar_a_todos": False}
        if not hasattr(self, "combinaciones_por_grupo") or not self.combinaciones_por_grupo:
            self.combinaciones_por_grupo = {}

        if not hasattr(self, "subgrupos") or not self.subgrupos:
            self.subgrupos = {}
            subgrupo_counter = 1
            for archivo in archivos:
                info = self._ffprobe_info(archivo)
                if info:
                    firma = self._get_language_signature(info)
                    if firma not in self.subgrupos:
                        self.subgrupos[firma] = subgrupo_counter
                        subgrupo_counter += 1

        ok = 0
        fail = 0
        total = len(archivos)
        errores = []
        self._log_message("===== INICIO PROCESAMIENTO =====")

        fue_cancelado = False
        archivos_exitosos = []
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._log_message("Cancelado por usuario")
                fue_cancelado = True
                break
            self.msg_queue.put(("PROGRESO", i, total))
            self._log_message(f"Archivo {i}/{total}: {os.path.basename(archivo)}")
            result = self._strip_tracks_processing(archivo, output_dir, errores)

            if self.cancelar_procesamiento:
                fue_cancelado = True
                errores = [err for err in errores if err[0] != archivo]
                break

            if isinstance(result, tuple):
                o, f = result
                if f == 0 and o > 0:
                    archivos_exitosos.append(archivo)
                ok += o
                fail += f
            elif result:
                archivos_exitosos.append(archivo)
                ok += 1
            else:
                fail += 1

        self._log_message("===== FIN PROCESAMIENTO =====")
        self.msg_queue.put(("FINALIZADO", ok, fail, errores, fue_cancelado, archivos_exitosos))
        self.procesando = False
        self.cancelar_procesamiento = False
        self._clear_subgroups()

    def process_queue(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return
        self._clear_subgroups()
        output = self.salida_var.get().strip()
        if not output:
            messagebox.showerror("Error", "Selecciona un directorio de salida")
            return
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        def callback_iniciar(archivos_validos):
            ok = self._preconfigure_queue_subgroups(archivos_validos, output_dir=output, forzar_reconfiguracion=True)
            if not ok:
                self._clear_subgroups()
                return

            archivos_a_procesar = [f for f in archivos_validos if f in set(self.lista.get(0, tk.END))]
            if not archivos_a_procesar:
                messagebox.showwarning("Cola vacía", "No quedan archivos para procesar.")
                self._clear_subgroups()
                return

            self.archivos_en_proceso = list(archivos_a_procesar)
            self._clear_log_and_progress("Preparando procesamiento de cola...")
            self._set_running_state(True)
            threading.Thread(target=self._process_queue_worker, args=(archivos_a_procesar, output), daemon=True).start()
            self._poll_ui_queue()

        self.precheck_queue("procesar_cola", archivos, output, callback_iniciar)

    def precheck_queue(self, tipo_proceso, archivos, output_dir, callback_exito):
        if tipo_proceso in ("procesar_cola",):
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                except Exception as exc:
                    messagebox.showerror("Error de carpeta de salida", f"No se puede crear el directorio de salida:\n{output_dir}\nDetalle: {exc}")
                    return
            if not os.access(output_dir, os.W_OK):
                messagebox.showerror("Error de permisos", f"El directorio de salida no tiene permisos de escritura:\n{output_dir}")
                return

        progreso = tk.Toplevel(self.root)
        progreso.title("Pre-verificando cola")
        progreso.geometry("500x140")
        progreso.transient(self.root)
        progreso.grab_set()
        self.root.attributes('-disabled', True)
        progreso.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == progreso and self.root.winfo_exists()) else None)

        progreso.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - progreso.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - progreso.winfo_height()) // 2
        progreso.geometry(f"+{x}+{y}")

        lbl = tk.Label(progreso, text="Pre-verificando archivos en la cola...", font=("Segoe UI", 10, "bold"))
        lbl.pack(pady=(18, 8))
        status = tk.Label(progreso, text="Preparando analisis...", font=("Segoe UI", 9))
        status.pack()
        pbar = ttk.Progressbar(progreso, mode="determinate", maximum=len(archivos), length=420)
        pbar.pack(pady=10)

        resultados = []

        def worker():
            infos = {}

            for i, archivo in enumerate(archivos, 1):
                status.config(text=f"{i}/{len(archivos)} - {os.path.basename(archivo)}")
                pbar["value"] = i
                progreso.update_idletasks()

                info = self._ffprobe_info(archivo)
                infos[archivo] = info

            for archivo in archivos:
                res = self._validate_file_for_precheck(archivo, tipo_proceso, output_dir, infos.get(archivo))
                resultados.append(res)

            progreso.destroy()
            self.root.after(0, lambda: self._handle_precheck_results(resultados, tipo_proceso, archivos, callback_exito))

        threading.Thread(target=worker, daemon=True).start()

    def _validate_file_for_precheck(self, archivo, tipo_proceso, output_dir, info=None):
        res = {
            "archivo": archivo,
            "basename": os.path.basename(archivo),
            "has_error": False,
            "has_warning": False,
            "errors": [],
            "warnings": []
        }

        if not os.path.exists(archivo):
            res["has_error"] = True
            res["errors"].append("El archivo no existe o la ruta no es valida.")
            return res

        if tipo_proceso in ("metadatos", "eliminar_subtitulos"):
            if not os.access(archivo, os.W_OK):
                res["has_error"] = True
                res["errors"].append("No se tiene permiso de escritura en el archivo original (necesario para modificar el archivo).")

        if info is None:
            info = self._ffprobe_info(archivo)
        if info is None:
            res["has_error"] = True
            res["errors"].append("ffprobe no pudo analizar el archivo. Podria estar corrupto o no ser soportado.")
            return res

        streams = info.get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

        if not video_streams:
            res["has_error"] = True
            res["errors"].append("El archivo no contiene ninguna pista de video.")

        if res["has_error"]:
            return res

        return res

    def _handle_precheck_results(self, resultados, tipo_proceso, archivos, callback_exito):
        con_errores = [r for r in resultados if r["has_error"]]
        con_advertencias = [r for r in resultados if r["has_warning"]]

        if not con_errores and not con_advertencias:
            callback_exito(archivos)
            return

        self._show_precheck_report(resultados, tipo_proceso, archivos, callback_exito)

    def verify_queue_files(self):
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showwarning("Sin archivos", "No hay archivos cargados")
            return

        if hasattr(self, "ffprobe_cache"):
            self.ffprobe_cache.clear()

        progreso = tk.Toplevel(self.root)
        progreso.title("Analizando cola")
        progreso.geometry("500x140")
        progreso.transient(self.root)
        progreso.grab_set()
        self.root.attributes('-disabled', True)
        progreso.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == progreso and self.root.winfo_exists()) else None)

        lbl = tk.Label(progreso, text="Analizando archivos de la cola...", font=("Segoe UI", 10, "bold"))
        lbl.pack(pady=(18, 8))
        status = tk.Label(progreso, text="Preparando...", font=("Segoe UI", 9))
        status.pack()
        pbar = ttk.Progressbar(progreso, mode="determinate", maximum=len(archivos), length=420)
        pbar.pack(pady=10)

        resultados = []

        def worker():
            for i, archivo in enumerate(archivos, 1):
                status.config(text=f"{i}/{len(archivos)} - {os.path.basename(archivo)}")
                pbar["value"] = i
                progreso.update_idletasks()

                res = self._validate_file_for_precheck(archivo, "procesar_cola", None)
                resultados.append(res)

            progreso.destroy()
            self.root.after(0, lambda: self._show_verification_results(resultados))

        threading.Thread(target=worker, daemon=True).start()

    def _strip_file_metadata(self, video_file, errores=None):
        video_file = Path(video_file)
        temp_output = video_file.parent / f"temp_{video_file.name}"
        info = self._ffprobe_info(video_file)

        is_mp4 = video_file.suffix.lower() in (".mp4", ".m4v")
        audio_args = ["-c:a", "copy"]
        sub_args = ["-c:s", "copy"]

        if is_mp4 and info and "streams" in info:
            audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
            if any(s.get("codec_name", "").lower() in INCOMPATIBLE_MP4_AUDIO_CODECS for s in audio_streams):
                audio_args = ["-c:a", "aac", "-b:a", "320k"]
            sub_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
            if sub_streams:
                if any(s.get("codec_name", "").lower() in BITMAP_SUB_CODECS for s in sub_streams):
                    sub_args = ["-sn"]
                else:
                    sub_args = ["-c:s", "mov_text"]

        mp4_faststart = ["-movflags", "+faststart"] if is_mp4 else []

        cmd = [
            self.ffmpeg_path,
            "-i",
            str(video_file),
            "-map",
            "0:V?",
            "-map",
            "0:a?",
        ]
        if sub_args != ["-sn"]:
            cmd.extend(["-map", "0:s?"])

        cmd.extend(["-c:v", "copy", *audio_args, *sub_args, *STRIP_METADATA_ARGS, *mp4_faststart, "-y", str(temp_output)])

        try:
            res = self._run_subprocess_cancellable(cmd, stdout_devnull=True)
            if res.returncode != 0:
                cmd_fb = [
                    self.ffmpeg_path,
                    "-i",
                    str(video_file),
                    "-map",
                    "0:V?",
                    "-map",
                    "0:a?",
                    "-c:v",
                    "copy",
                    *audio_args,
                    "-sn",
                    *STRIP_METADATA_ARGS,
                    *mp4_faststart,
                    "-y",
                    str(temp_output),
                ]
                res = self._run_subprocess_cancellable(cmd_fb, stdout_devnull=True)

            if res.returncode != 0:
                err_detail = ""
                if hasattr(res, "stderr") and res.stderr:
                    lines = [l.strip() for l in res.stderr.splitlines() if l.strip()]
                    if lines:
                        err_detail = f" Detalle: {' '.join(lines[-2:])}"
                if errores is not None:
                    errores.append((str(video_file), f"Fallo al ejecutar ffmpeg para eliminar metadatos (código de salida: {res.returncode}).{err_detail}"))
                return False
            if temp_output.exists():
                video_file.unlink()
                ext = video_file.suffix
                self._invalidate_file_cache(video_file)
                if ext != ext.lower():
                    temp_output.rename(video_file.with_suffix(ext.lower()))
                else:
                    temp_output.rename(video_file)
                return True
            if errores is not None:
                errores.append((str(video_file), "No se pudo crear o renombrar el archivo temporal modificado."))
            return False
        except Exception as exc:
            if errores is not None:
                errores.append((str(video_file), f"Error inesperado al eliminar metadatos: {exc}"))
            return False
        finally:
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except Exception:
                    pass

    def _strip_metadata_worker(self, archivos):
        self.procesando = True
        self.cancelar_procesamiento = False

        ok = 0
        fail = 0
        total = len(archivos)
        errores = []
        self._log_message("===== INICIO ELIMINACIÓN METADATOS =====")

        fue_cancelado = False
        archivos_exitosos = []
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._log_message("Cancelado por usuario")
                fue_cancelado = True
                break
            self.msg_queue.put(("PROGRESO", i, total))
            nombre_archivo = os.path.basename(archivo)
            self._log_message(f"Eliminando metadatos {i}/{total}: {nombre_archivo}")
            self._record_activity("procesando", nombre_archivo, "Eliminar meta", "Limpiando metadatos...", item_key=f"meta:{archivo}")
            result = self._strip_file_metadata(archivo, errores)

            if self.cancelar_procesamiento:
                fue_cancelado = True
                errores = [err for err in errores if err[0] != archivo]
                break

            if result:
                archivos_exitosos.append(archivo)
                self._record_activity("exito", nombre_archivo, "Eliminar meta", "Metadatos eliminados", item_key=f"meta:{archivo}")
                ok += 1
            else:
                err_txt = next((e[1] for e in reversed(errores) if e[0] == archivo), "Error al limpiar metadatos")
                self._record_activity("error", nombre_archivo, "Eliminar meta", err_txt, item_key=f"meta:{archivo}")
                fail += 1

        self._log_message("===== FIN ELIMINACIÓN METADATOS =====")
        self.msg_queue.put(("FINALIZADO", ok, fail, errores, fue_cancelado, archivos_exitosos))
        self.procesando = False
        self.cancelar_procesamiento = False

    def strip_metadata(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        confirm = messagebox.askyesno(
            "Confirmar",
            f"Se eliminarán los metadatos en {len(archivos)} archivo(s).\nEsta acción modifica los originales.",
            icon="warning",
        )
        if not confirm:
            return

        def callback_iniciar(archivos_validos):
            self.archivos_en_proceso = list(archivos_validos)
            self._clear_log_and_progress("Preparando eliminación de metadatos...")
            self._set_running_state(True)
            threading.Thread(target=self._strip_metadata_worker, args=(archivos_validos,), daemon=True).start()
            self._poll_ui_queue()

        self.precheck_queue("eliminar_metadatos", archivos, None, callback_iniciar)

    def _strip_file_subtitles(self, video_file, errores=None):
        video_file = Path(video_file)
        info = self._ffprobe_info(video_file)
        if info is None:
            if errores is not None:
                errores.append((str(video_file), "No se pudo leer streams con ffprobe."))
            return False

        subtitle_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "subtitle" and not s.get("is_external")]
        if not subtitle_streams:
            self._log_message("  -> El archivo no contiene subtítulos internos. Saltando.")
            return True

        temp_output = video_file.parent / f"temp_{video_file.name}"
        is_mp4 = video_file.suffix.lower() in (".mp4", ".m4v")
        audio_args = ["-c:a", "copy"]

        if is_mp4 and info and "streams" in info:
            audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
            if any(s.get("codec_name", "").lower() in INCOMPATIBLE_MP4_AUDIO_CODECS for s in audio_streams):
                audio_args = ["-c:a", "aac", "-b:a", "320k"]

        cmd = [
            self.ffmpeg_path,
            "-i",
            str(video_file),
            "-map",
            "0:v?",
            "-map",
            "0:a?",
            "-c:v",
            "copy",
            *audio_args,
            "-sn",
            "-y",
            str(temp_output),
        ]
        try:
            res = self._run_subprocess_cancellable(cmd, stdout_devnull=True)
            rc = res.returncode
            if rc > 2147483647: rc -= 4294967296
            if rc != 0:
                err_detail = ""
                if hasattr(res, "stderr") and res.stderr:
                    lines = [l.strip() for l in res.stderr.splitlines() if l.strip()]
                    if lines:
                        err_detail = f" Detalle: {' '.join(lines[-2:])}"
                if errores is not None:
                    errores.append((str(video_file), f"Fallo al ejecutar ffmpeg para eliminar subtítulos (código de salida: {rc}).{err_detail}"))
                return False
            if temp_output.exists():
                video_file.unlink()
                ext = video_file.suffix
                self._invalidate_file_cache(video_file)
                if ext != ext.lower():
                    temp_output.rename(video_file.with_suffix(ext.lower()))
                else:
                    temp_output.rename(video_file)
                return True
            if errores is not None:
                errores.append((str(video_file), "No se pudo crear o renombrar el archivo temporal modificado."))
            return False
        except Exception as exc:
            if errores is not None:
                errores.append((str(video_file), f"Error inesperado al eliminar subtítulos: {exc}"))
            return False
        finally:
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except Exception:
                    pass

    def _strip_subtitles_worker(self, archivos):
        self.procesando = True
        self.cancelar_procesamiento = False

        ok = 0
        fail = 0
        total = len(archivos)
        errores = []
        self._log_message("===== INICIO ELIMINACIÓN DE SUBTÍTULOS =====")

        fue_cancelado = False
        archivos_exitosos = []
        for i, archivo in enumerate(archivos, 1):
            if self.cancelar_procesamiento:
                self._log_message("Cancelado por usuario")
                fue_cancelado = True
                break
            self.msg_queue.put(("PROGRESO", i, total))
            nombre_archivo = os.path.basename(archivo)
            self._log_message(f"Eliminando subs {i}/{total}: {nombre_archivo}")
            self._record_activity("procesando", nombre_archivo, "Eliminar subs", "Eliminando subtítulos...", item_key=f"subs:{archivo}")
            result = self._strip_file_subtitles(archivo, errores)

            if self.cancelar_procesamiento:
                fue_cancelado = True
                errores = [err for err in errores if err[0] != archivo]
                break

            if result:
                archivos_exitosos.append(archivo)
                self._record_activity("exito", nombre_archivo, "Eliminar subs", "Subtítulos eliminados", item_key=f"subs:{archivo}")
                ok += 1
            else:
                err_txt = next((e[1] for e in reversed(errores) if e[0] == archivo), "Error al eliminar subtítulos")
                self._record_activity("error", nombre_archivo, "Eliminar subs", err_txt, item_key=f"subs:{archivo}")
                fail += 1

        self._log_message("===== FIN ELIMINACIÓN DE SUBTÍTULOS =====")
        self.msg_queue.put(("FINALIZADO", ok, fail, errores, fue_cancelado, archivos_exitosos))
        self.procesando = False
        self.cancelar_procesamiento = False

    def strip_subtitles(self):
        if self.procesando:
            messagebox.showwarning("En curso", "Ya hay un proceso activo")
            return
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video")
            return

        confirm = messagebox.askyesno(
            "Confirmar",
            f"Se eliminarán todos los subtítulos de {len(archivos)} archivo(s).\nEsta acción modifica los archivos originales.",
            icon="warning",
        )
        if not confirm:
            return

        def callback_iniciar(archivos_validos):
            self.archivos_en_proceso = list(archivos_validos)
            self._clear_log_and_progress("Preparando eliminación de subtítulos...")
            self._set_running_state(True)
            threading.Thread(target=self._strip_subtitles_worker, args=(archivos_validos,), daemon=True).start()
            self._poll_ui_queue()

        self.precheck_queue("eliminar_subtitulos", archivos, None, callback_iniciar)

    def cancel_processing(self):
        if not self.procesando:
            messagebox.showinfo("Sin proceso", "No hay procesamiento activo")
            return
        if messagebox.askyesno("Cancelar todo", "Deseas cancelar el procesamiento actual y detener toda la cola de videos?"):
            self.cancelar_procesamiento = True
            self._clear_subgroups()
            if self.proceso_actual:
                try:
                    self.proceso_actual.terminate()
                except Exception:
                    pass
            self.btn_cancelar.config(state=tk.DISABLED)
            self._log_message("Solicitud de cancelacion enviada...")

    def _run_subprocess_cancellable(self, cmd, stdout_devnull=False):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        stderr_lines = []
        def _read_stderr(pipe):
            try:
                for line in iter(pipe.readline, ''):
                    if line:
                        stderr_lines.append(line)
            except Exception:
                pass
            finally:
                pipe.close()

        self.proceso_actual = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo
        )

        stderr_thread = threading.Thread(target=_read_stderr, args=(self.proceso_actual.stderr,), daemon=True)
        stderr_thread.start()

        import time
        while True:
            if self.cancelar_procesamiento:
                try:
                    self.proceso_actual.terminate()
                    self.proceso_actual.wait(timeout=1.5)
                except Exception:
                    try:
                        self.proceso_actual.kill()
                    except Exception:
                        pass
                stderr_thread.join(timeout=0.5)
                return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="".join(stderr_lines))

            ret = self.proceso_actual.poll()
            if ret is not None:
                stderr_thread.join(timeout=0.5)
                if ret > 0x7FFFFFFF:
                    ret = ret - 0x100000000
                return subprocess.CompletedProcess(cmd, returncode=ret, stdout="", stderr="".join(stderr_lines))

            time.sleep(0.1)

