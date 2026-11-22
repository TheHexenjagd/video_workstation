"""Dynamic output subfolder pattern builder dialog."""

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from video_workstation.media.paths import resolve_subfolder_pattern as _resolver_patron_subcarpeta_helper
from video_workstation.utils.binaries import get_default_videos_dir as obtener_directorio_videos_defecto


class PathBuilderDialogMixin:
    """Mixin providing the dynamic output path builder dialog."""

    def _resolve_subfolder_pattern(self, filepath, info, label, audio_indices, sub_indices):
        return _resolver_patron_subcarpeta_helper(
            self.var_nombre_subcarpeta.get(),
            filepath,
            info,
            label,
            audio_indices,
            sub_indices,
        )

    def _open_path_builder(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Constructor de Ruta de Salida")
        dialog.geometry("750x660")
        dialog.minsize(720, 620)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)
        dialog.configure(bg="#F3F7FF")

        tk.Label(dialog, text="Constructor de Ruta de Salida", font=("Segoe UI", 12, "bold"), bg="#F3F7FF", fg="#1F2A44").pack(pady=(12, 6))
        tk.Label(dialog, text="Haz clic en las banderas para agregarlas al patrón de subcarpeta:", font=("Segoe UI", 9), bg="#F3F7FF", fg="#5C6B8A").pack(pady=(0, 10))

        patron_var = tk.StringVar(value=self.var_nombre_subcarpeta.get())
        entry = tk.Entry(dialog, textvariable=patron_var, font=("Consolas", 11), bg="#FFFFFF", fg="#1F2A44", relief=tk.SOLID, bd=1)
        entry.pack(fill=tk.X, padx=20, pady=8)
        entry.focus_set()

        presets_frame = tk.Frame(dialog, bg="#F3F7FF")
        presets_frame.pack(fill=tk.X, padx=20, pady=(4, 8))

        tk.Label(presets_frame, text="Presets:", font=("Segoe UI", 9, "bold"), bg="#F3F7FF", fg="#2B3A57").pack(side=tk.LEFT, padx=(0, 6))

        try:
            presets_data = json.loads(self.config_ini.get("Options", "presets", fallback='[]'))
        except Exception:
            presets_data = []

        presets_var = tk.StringVar()
        cb_presets = ttk.Combobox(presets_frame, values=presets_data, textvariable=presets_var, state="readonly", width=40)
        cb_presets.pack(side=tk.LEFT, padx=6)
        if presets_data:
            presets_var.set(presets_data[0])

        def on_preset_selected(*_):
            selected = presets_var.get()
            if selected:
                patron_var.set(selected)

        cb_presets.bind("<<ComboboxSelected>>", on_preset_selected)

        def guardar_nuevo_preset():
            nuevo = patron_var.get().strip()
            if not nuevo:
                return
            try:
                curr = json.loads(self.config_ini.get("Options", "presets", fallback='[]'))
            except Exception:
                curr = []

            if nuevo not in curr:
                curr.append(nuevo)
                if "Options" not in self.config_ini:
                    self.config_ini["Options"] = {}
                self.config_ini["Options"]["presets"] = json.dumps(curr)
                self._save_config()
                self.cb_nombre_subcarpeta["values"] = curr
                cb_presets["values"] = curr
                presets_var.set(nuevo)
                messagebox.showinfo("Preset Guardado", f"Se ha guardado el preset:\n{nuevo}", parent=dialog)

        btn_add_preset = tk.Button(
            presets_frame,
            text="Guardar actual",
            command=guardar_nuevo_preset,
            bg="#27AE60",
            fg="white",
            activebackground="#27AE60",
            activeforeground="white",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_add_preset.pack(side=tk.LEFT, padx=6)

        def eliminar_preset_seleccionado():
            seleccionado = cb_presets.get()
            if not seleccionado:
                return
            try:
                curr = json.loads(self.config_ini.get("Options", "presets", fallback='[]'))
            except Exception:
                curr = []

            if seleccionado in curr:
                curr.remove(seleccionado)
                if "Options" not in self.config_ini:
                    self.config_ini["Options"] = {}
                self.config_ini["Options"]["presets"] = json.dumps(curr)
                self._save_config()
                self.cb_nombre_subcarpeta["values"] = curr
                cb_presets["values"] = curr
                if curr:
                    presets_var.set(curr[0])
                    patron_var.set(curr[0])
                else:
                    presets_var.set("")
                    patron_var.set("")
                messagebox.showinfo("Preset Eliminado", "El preset seleccionado ha sido eliminado.", parent=dialog)

        btn_del_preset = tk.Button(
            presets_frame,
            text="Eliminar",
            command=eliminar_preset_seleccionado,
            bg="#EB5757",
            fg="white",
            activebackground="#EB5757",
            activeforeground="white",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_del_preset.pack(side=tk.LEFT, padx=6)

        flags_frame = tk.LabelFrame(dialog, text="Banderas Disponibles", font=("Segoe UI", 9, "bold"), bg="#FFFFFF", fg="#2B3A57", padx=10, pady=10)
        flags_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(4, 10))
        flags_frame.configure(relief=tk.GROOVE)

        flags = [
            ("{name}", "Nombre original del video"),
            ("{folder}", "Nombre de la carpeta contenedora del video"),
            ("{label}", "Etiqueta/Versión (ej: ESP_subENG, hardcoded)"),
            ("{audio_langs}", "Idiomas de audio resultantes (ej: ESP_ENG)"),
            ("{sub_langs}", "Idiomas de subtítulos resultantes (ej: SPA, NONE)"),
            ("{codec_v}", "Codec de video (ej: h264, hevc)"),
            ("{codec_a}", "Codec de audio (ej: aac, ac3)"),
            ("{resolution}", "Resolución del video (ej: 1080p, 720p)"),
        ]

        def insertar_flag(flag):
            pos = entry.index(tk.INSERT)
            entry.insert(pos, flag)
            entry.focus_set()
            actualizar_preview()

        for i, (flag, desc) in enumerate(flags):
            row = tk.Frame(flags_frame, bg="#FFFFFF")
            row.pack(fill=tk.X, pady=3)

            btn = tk.Button(
                row,
                text=flag,
                command=lambda f=flag: insertar_flag(f),
                bg="#2D9CDB",
                fg="white",
                activebackground="#2D9CDB",
                activeforeground="white",
                relief=tk.FLAT,
                width=16,
                font=("Consolas", 9, "bold"),
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=(0, 10))

            tk.Label(row, text=desc, font=("Segoe UI", 9), bg="#FFFFFF", fg="#5C6B8A").pack(side=tk.LEFT)

        preview_frame = tk.Frame(dialog, bg="#E5ECF9", padx=10, pady=10)
        btm = tk.Frame(dialog, bg="#F3F7FF")

        btm.pack(side=tk.BOTTOM, pady=(5, 12))
        preview_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=10)

        tk.Label(preview_frame, text="Vista previa de ruta resuelta:", font=("Segoe UI", 9, "bold"), bg="#E5ECF9", fg="#2B3A57").pack(anchor=tk.W)
        preview_lbl = tk.Label(preview_frame, text="", font=("Consolas", 9), bg="#E5ECF9", fg="#1F2A44", wraplength=680, justify=tk.LEFT)
        preview_lbl.pack(anchor=tk.W, pady=(4, 0))

        def actualizar_preview(*_):
            archivos = list(self.lista.get(0, tk.END))
            patron = patron_var.get()

            dummy_info = {
                "streams": [
                    {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "index": 0},
                    {"codec_type": "audio", "codec_name": "ac3", "index": 1, "tags": {"language": "spa"}},
                    {"codec_type": "audio", "codec_name": "aac", "index": 2, "tags": {"language": "eng"}},
                    {"codec_type": "subtitle", "codec_name": "subrip", "index": 3, "tags": {"language": "eng"}}
                ]
            }

            video_name = "Ejemplo_Video"
            info = dummy_info
            audio_indices = [1, 2]
            sub_indices = [3]

            if archivos:
                video_name = Path(archivos[0]).stem
                real_info = self._ffprobe_info(archivos[0])
                if real_info:
                    info = real_info
                    audio_indices = [s["index"] for s in info["streams"] if s.get("codec_type") == "audio"]
                    sub_indices = [s["index"] for s in info["streams"] if s.get("codec_type") == "subtitle"]

            old_val = self.var_nombre_subcarpeta.get()
            self.var_nombre_subcarpeta.set(patron)
            resolved = self._resolve_subfolder_pattern(f"C:/ruta/de/ejemplo/{video_name}.mp4", info, "ESP_subENG", audio_indices, sub_indices)
            self.var_nombre_subcarpeta.set(old_val)

            base_dir = self.salida_var.get().strip() or obtener_directorio_videos_defecto()
            sub_dir = f"{resolved}/" if resolved else ""
            preview_lbl.config(text=f"{base_dir}/{sub_dir}{video_name}.mp4")

        patron_var.trace_add("write", actualizar_preview)
        actualizar_preview()

        def aceptar():
            self.var_nombre_subcarpeta.set(patron_var.get())
            dialog.destroy()

        tk.Button(btm, text="Guardar", command=aceptar, bg="#27AE60", fg="white", width=12, relief=tk.FLAT, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=6)
        tk.Button(btm, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=12, relief=tk.FLAT, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=6)

