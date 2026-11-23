"""Dynamic output subfolder pattern builder dialog."""

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from video_workstation.media.paths import resolve_subfolder_pattern as _resolver_patron_subcarpeta_helper
from video_workstation.ui.theme import get_theme
from video_workstation.ui.widgets import RoundedButton, center_window
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
        dialog.withdraw()
        dialog.title("Constructor de Ruta de Salida")
        dialog.minsize(720, 620)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)
        t = get_theme(self.theme_var.get())
        dialog.configure(bg=t["bg_app"])

        hdr_card = tk.Frame(dialog, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        hdr_card.pack(fill=tk.X, padx=16, pady=(12, 10))
        hdr_in = tk.Frame(hdr_card, bg=t["bg_surface"])
        hdr_in.pack(fill=tk.X, padx=14, pady=10)
        tk.Label(hdr_in, text="VW", font=("Segoe UI", 10, "bold"), bg=t["accent"], fg="#FFFFFF", padx=7, pady=2).pack(side=tk.LEFT)
        hdr_txt = tk.Frame(hdr_in, bg=t["bg_surface"])
        hdr_txt.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        tk.Label(hdr_txt, text="Constructor de Ruta de Salida", font=("Segoe UI", 11, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W)
        tk.Label(hdr_txt, text="Haz clic en las banderas para agregarlas al patrón de subcarpeta:", font=("Segoe UI", 9), bg=t["bg_surface"], fg=t["fg_muted"]).pack(anchor=tk.W, pady=(2, 0))

        cfg_card = tk.Frame(dialog, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        cfg_card.pack(fill=tk.X, padx=16, pady=(0, 10))

        patron_var = tk.StringVar(value=self.var_nombre_subcarpeta.get())
        entry = tk.Entry(cfg_card, textvariable=patron_var, font=("Consolas", 10), bg=t["bg_input"], fg=t["fg_primary"], insertbackground=t["fg_primary"], highlightthickness=1, highlightbackground=t["border"], relief=tk.FLAT)
        entry.pack(fill=tk.X, padx=14, pady=(12, 8))
        entry.focus_set()

        presets_frame = tk.Frame(cfg_card, bg=t["bg_surface"])
        presets_frame.pack(fill=tk.X, padx=14, pady=(0, 12))

        tk.Label(presets_frame, text="Presets:", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(side=tk.LEFT, padx=(0, 6))

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

        btn_add_preset = RoundedButton(
            presets_frame,
            text="Guardar actual",
            command=guardar_nuevo_preset,
            bg=t["btn_success"],
            fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"),
            width=105,
            height=26,
        )
        btn_add_preset.pack(side=tk.LEFT, padx=3)

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

        btn_del_preset = RoundedButton(
            presets_frame,
            text="Eliminar",
            command=eliminar_preset_seleccionado,
            bg=t["btn_danger"],
            fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"),
            width=75,
            height=26,
        )
        btn_del_preset.pack(side=tk.LEFT, padx=3)

        flags_card = tk.Frame(dialog, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        flags_card.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 10))

        flags_hdr = tk.Frame(flags_card, bg=t["bg_surface"])
        flags_hdr.pack(fill=tk.X, padx=14, pady=(10, 6))
        tk.Label(flags_hdr, text="Banderas Disponibles", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W)
        tk.Frame(flags_card, height=1, bg=t["border"]).pack(fill=tk.X, padx=14, pady=(0, 8))

        flags_body = tk.Frame(flags_card, bg=t["bg_surface"])
        flags_body.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

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
            row = tk.Frame(flags_body, bg=t["bg_surface"])
            row.pack(fill=tk.X, pady=2)

            btn = RoundedButton(
                row,
                text=flag,
                command=lambda f=flag: insertar_flag(f),
                bg=t["accent"],
                fg="#FFFFFF",
                font=("Consolas", 9, "bold"),
                width=135,
                height=24,
            )
            btn.pack(side=tk.LEFT, padx=(0, 10))

            tk.Label(row, text=desc, font=("Segoe UI", 9), bg=t["bg_surface"], fg=t["fg_secondary"]).pack(side=tk.LEFT)

        preview_card = tk.Frame(dialog, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        preview_card.pack(fill=tk.X, padx=16, pady=(0, 10))

        tk.Label(preview_card, text="Vista previa de ruta resuelta:", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W, padx=14, pady=(8, 2))
        preview_lbl = tk.Label(preview_card, text="", font=("Consolas", 9), bg=t["bg_surface"], fg=t["accent"], wraplength=680, justify=tk.LEFT)
        preview_lbl.pack(anchor=tk.W, padx=14, pady=(0, 8))

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

        btm = tk.Frame(dialog, bg=t["bg_app"])
        btm.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 14))

        btn_container = tk.Frame(btm, bg=t["bg_app"])
        btn_container.pack(anchor=tk.CENTER)

        def aceptar():
            self.var_nombre_subcarpeta.set(patron_var.get())
            dialog.destroy()

        RoundedButton(btn_container, text="Guardar", command=aceptar, bg=t["btn_success"], fg="#FFFFFF", font=("Segoe UI", 9, "bold"), width=110, height=34).pack(side=tk.LEFT, padx=8)
        RoundedButton(btn_container, text="Cancelar", command=dialog.destroy, bg=t["btn_secondary_bg"], fg=t["btn_secondary_fg"], font=("Segoe UI", 9, "bold"), width=100, height=34).pack(side=tk.LEFT, padx=8)

        center_window(dialog, 750, 660, self.root)

