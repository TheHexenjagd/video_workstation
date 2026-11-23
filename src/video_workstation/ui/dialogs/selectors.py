"""Track and output-combination selector dialogs."""

import os
import tkinter as tk
from tkinter import messagebox, ttk

from video_workstation.constants import BITMAP_SUB_CODECS
from video_workstation.media.ffprobe import (
    get_track_identifier as obtener_identificador_pista,
    is_hdr_video as _video_es_hdr,
)
from video_workstation.ui.theme import get_theme
from video_workstation.ui.widgets import ModernCheckbutton, center_window


class TrackSelectorDialogMixin:
    """Mixin providing track and version-combination selection dialogs."""

    def _show_track_selector(self, info, filename):
        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]

        if len(audio_streams) <= 1 and len(subtitle_streams) == 0:
            return {
                "ok": True,
                "audio": obtener_identificador_pista(audio_streams[0]) if audio_streams else None,
                "subtitle": "NINGUNO",
                "aplicar_todos": False,
            }

        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title(f"Seleccion de pistas - {os.path.basename(filename)}")
        center_window(dialog, 740, 620, self.root)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)

        resultado = {"ok": False, "audio": None, "subtitle": "NINGUNO", "aplicar_todos": False}

        tk.Label(dialog, text=f"Archivo: {os.path.basename(filename)}", font=("Segoe UI", 10, "bold")).pack(pady=(10, 6))

        btns = tk.Frame(dialog)
        btns.pack(side=tk.BOTTOM, pady=10)

        t_sel = get_theme(self.theme_var.get())
        apply_all = tk.BooleanVar(value=False)
        ModernCheckbutton(
            dialog,
            text="Aplicar seleccion a todos los archivos",
            variable=apply_all,
            bg=dialog.cget("bg"),
            fg=t_sel["fg_secondary"],
            activeforeground=t_sel["fg_primary"],
            selectcolor=t_sel["bg_input"],
            accent=t_sel["accent"],
            border=t_sel["border_strong"],
        ).pack(side=tk.BOTTOM, pady=6)

        body_container = tk.Frame(dialog)
        body_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10)

        canvas = tk.Canvas(body_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        body = tk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=body, anchor="nw")

        def _actualizar_scroll_pistas(event=None):
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if not bbox:
                return
            content_height = bbox[3] - bbox[1]
            canvas_height = canvas.winfo_height()
            canvas.configure(scrollregion=(0, 0, bbox[2], content_height))
            if content_height > canvas_height and canvas_height > 1:
                if not scrollbar.winfo_ismapped():
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                if scrollbar.winfo_ismapped():
                    scrollbar.pack_forget()
                canvas.yview_moveto(0)

        body.bind("<Configure>", _actualizar_scroll_pistas)

        def _on_canvas_configure(e):
            canvas.itemconfig(canvas_window, width=e.width)
            _actualizar_scroll_pistas()

        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            bbox = canvas.bbox("all")
            if not bbox:
                return
            content_height = bbox[3] - bbox[1]
            canvas_height = canvas.winfo_height()
            if content_height <= canvas_height:
                return
            delta = int(-1 * (event.delta / 120))
            canvas.yview_scroll(delta, "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        dialog.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget == dialog else None, add="+")

        audio_var = tk.StringVar(value=obtener_identificador_pista(audio_streams[0]) if audio_streams else "")
        sub_var = tk.StringVar(value="NINGUNO")

        lf_audio = tk.LabelFrame(body, text="Audio", font=("Segoe UI", 9, "bold"))
        lf_audio.pack(fill=tk.BOTH, expand=True, pady=6)
        for i, s in enumerate(audio_streams):
            tags = s.get("tags", {})
            title = tags.get("title") or f"Audio {i + 1}"
            lang = tags.get("language", "und")
            codec = s.get("codec_name", "unknown")
            tk.Radiobutton(lf_audio, text=f"{title} ({lang}) - {codec}", variable=audio_var, value=obtener_identificador_pista(s), anchor=tk.W).pack(fill=tk.X, padx=6, pady=2)

        lf_sub = tk.LabelFrame(body, text="Subtitulos", font=("Segoe UI", 9, "bold"))
        lf_sub.pack(fill=tk.BOTH, expand=True, pady=6)
        tk.Radiobutton(lf_sub, text="Sin subtitulos", variable=sub_var, value="NINGUNO", anchor=tk.W).pack(fill=tk.X, padx=6, pady=2)
        for i, s in enumerate(subtitle_streams):
            tags = s.get("tags", {})
            title = tags.get("title") or f"Subtitulo {i + 1}"
            lang = tags.get("language", "und")
            codec = s.get("codec_name", "unknown")
            tk.Radiobutton(lf_sub, text=f"{title} ({lang}) - {codec}", variable=sub_var, value=obtener_identificador_pista(s), anchor=tk.W).pack(fill=tk.X, padx=6, pady=2)

        dialog.after(50, _actualizar_scroll_pistas)

        def aceptar():
            resultado["ok"] = True
            resultado["audio"] = audio_var.get()
            resultado["subtitle"] = sub_var.get()
            resultado["aplicar_todos"] = apply_all.get()
            dialog.destroy()

        tk.Button(btns, text="Aceptar", command=aceptar, bg="#2D9CDB", fg="white", width=14).pack(side=tk.LEFT, padx=6)
        tk.Button(btns, text="Cancelar", command=dialog.destroy, bg="#EB5757", fg="white", width=14).pack(side=tk.LEFT, padx=6)

        dialog.wait_window()
        if not resultado["ok"]:
            if self.cancelar_procesamiento:
                return resultado

            ans = messagebox.askyesnocancel(
                "Cancelar proceso",
                "¿Deseas cancelar todo el procesamiento?\n\n"
                "Sí: Cancela toda la cola de videos.\n"
                "No: Salta este archivo y continúa con el siguiente.\n"
                "Cancelar: Vuelve a la selección de pistas.",
                parent=self.root
            )
            if ans is True:
                self.cancelar_procesamiento = True
                resultado["ok"] = False
            elif ans is False:
                resultado["ok"] = False
            else:
                if self.cancelar_procesamiento:
                    return resultado
                return self._show_track_selector(info, filename)
        return resultado

    def _show_combination_selector(self, info, filename, subgrupo_label=None, modo_previo=False):
        audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]

        if not audio_streams and not subtitle_streams:
            return {"ok": True, "combinaciones": [], "aplicar_todos": True if modo_previo else False}

        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        sg_title = ""
        if subgrupo_label:
            # Mantener el título conciso para no desplazar el nombre del archivo
            sg_title = f" - {subgrupo_label.split(' | ')[0]}"
        dialog.title(f"Versiones a generar{sg_title} - {os.path.basename(filename)}")
        center_window(dialog, 900, 620, self.root)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)

        t = get_theme(self.theme_var.get())
        dialog.configure(bg=t["bg_app"])
        dialog._vw_themed = True
        resultado = {"ok": False, "combinaciones": [], "aplicar_todos": False}
        combinaciones = []

        hdr_card = tk.Frame(dialog, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        hdr_card.pack(fill=tk.X, padx=16, pady=(14, 10))
        hdr_in = tk.Frame(hdr_card, bg=t["bg_surface"])
        hdr_in.pack(fill=tk.X, padx=14, pady=10)
        tk.Label(hdr_in, text="VW", font=("Segoe UI", 10, "bold"), bg=t["accent"], fg="#FFFFFF", padx=7, pady=2).pack(side=tk.LEFT)
        hdr_txt = tk.Frame(hdr_in, bg=t["bg_surface"])
        hdr_txt.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        if subgrupo_label:
            tk.Label(hdr_txt, text=subgrupo_label, font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["accent"], anchor=tk.W, wraplength=760, justify=tk.LEFT).pack(anchor=tk.W)
            tk.Label(hdr_txt, text="Marca las pistas deseadas y pulsa Aceptar (o agrégalas como versiones múltiples).", font=("Segoe UI", 8), bg=t["bg_surface"], fg=t["fg_muted"]).pack(anchor=tk.W)
        else:
            tk.Label(hdr_txt, text="Marca las pistas deseadas y pulsa Aceptar", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W)

        # Empaquetar la barra inferior primero para garantizar que los botones Aceptar/Cancelar nunca queden fuera de pantalla
        bottom = tk.Frame(dialog, bg=t["bg_app"])
        bottom.pack(side=tk.BOTTOM, pady=(4, 14))

        apply_all = tk.BooleanVar(value=True if modo_previo else False)
        chk_text = "Aplicar esta configuración a todos los archivos de este subgrupo" if modo_previo else "Aplicar esta configuración a todos los similares (mismo subgrupo)"
        ModernCheckbutton(
            dialog,
            text=chk_text,
            variable=apply_all,
            bg=t["bg_app"],
            fg=t["fg_secondary"],
            activeforeground=t["fg_primary"],
            selectcolor=t["bg_input"],
            accent=t["accent"],
            border=t["border_strong"],
        ).pack(side=tk.BOTTOM, pady=(4, 2))

        body = tk.Frame(dialog, bg=t["bg_app"])
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        left = tk.Frame(body, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        tk.Label(left, text="Pistas disponibles", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W, padx=14, pady=(12, 8))
        tk.Frame(left, height=1, bg=t["border"]).pack(fill=tk.X, padx=14, pady=(0, 8))

        var_hardsub = tk.BooleanVar(value=False)
        cb_hardsub = ModernCheckbutton(
            left,
            text="Hacer hardsub (Incrustar)",
            variable=var_hardsub,
            font=("Segoe UI", 9, "bold"),
            bg=t["bg_surface"],
            fg=t["danger"],
            activeforeground=t["danger"],
            selectcolor=t["bg_input"],
            accent=t["accent"],
            border=t["border_strong"],
            disabled_fg=t["fg_muted"],
            state=tk.DISABLED,
        )
        cb_hardsub.pack(side=tk.BOTTOM, anchor=tk.W, padx=14, pady=(6, 10))

        tracks_container = tk.Frame(left, bg=t["bg_surface"])
        tracks_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10)

        canvas = tk.Canvas(tracks_container, bg=t["bg_surface"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(tracks_container, orient="vertical", command=canvas.yview, style="Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollable_frame = tk.Frame(canvas, bg=t["bg_surface"])
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _actualizar_scroll_combos(event=None):
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if not bbox:
                return
            content_height = bbox[3] - bbox[1]
            canvas_height = canvas.winfo_height()
            canvas.configure(scrollregion=(0, 0, bbox[2], content_height))
            if content_height > canvas_height and canvas_height > 1:
                if not scrollbar.winfo_ismapped():
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                if scrollbar.winfo_ismapped():
                    scrollbar.pack_forget()
                canvas.yview_moveto(0)

        scrollable_frame.bind("<Configure>", _actualizar_scroll_combos)

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
            _actualizar_scroll_combos()

        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            bbox = canvas.bbox("all")
            if not bbox:
                return
            content_height = bbox[3] - bbox[1]
            canvas_height = canvas.winfo_height()
            if content_height <= canvas_height:
                return
            delta = int(-1 * (event.delta / 120))
            canvas.yview_scroll(delta, "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        dialog.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget == dialog else None, add="+")

        audio_vars = []
        sub_vars = []

        es_hdr = _video_es_hdr(info)

        def actualizar_estado_hardsub():
            aud_sel = [s for v, s in audio_vars if v.get()]
            sub_sel = [s for v, s in sub_vars if v.get()]
            if es_hdr:
                var_hardsub.set(False)
                cb_hardsub.config(state=tk.DISABLED, text="Hacer hardsub (Desactivado: video HDR)")
            elif len(aud_sel) == 1 and len(sub_sel) == 1:
                sub_codec = (sub_sel[0].get("codec_name") or "").lower()
                if sub_codec in BITMAP_SUB_CODECS:
                    var_hardsub.set(False)
                    cb_hardsub.config(state=tk.DISABLED, text="Hacer hardsub (Desactivado: subtítulo bitmap)")
                else:
                    cb_hardsub.config(state=tk.NORMAL, text="Hacer hardsub (Incrustar)")
                    var_hardsub.set(True)
            else:
                var_hardsub.set(False)
                cb_hardsub.config(state=tk.DISABLED, text="Hacer hardsub (Incrustar)")

        tk.Label(scrollable_frame, text="Audio", bg=t["bg_surface"], fg=t["success"], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=6, pady=(6, 2))
        for i, s in enumerate(audio_streams):
            tags = s.get("tags") or {}
            title = tags.get("title") or f"Audio {i + 1}"
            lang = tags.get("language", "und")
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_: actualizar_estado_hardsub())
            audio_vars.append((var, s))
            ModernCheckbutton(
                scrollable_frame,
                text=f"{title} ({lang})",
                variable=var,
                bg=t["bg_surface"],
                fg=t["fg_primary"],
                activeforeground=t["fg_primary"],
                selectcolor=t["bg_input"],
                accent=t["accent"],
                border=t["border_strong"],
            ).pack(anchor=tk.W, padx=8, pady=2)

        tk.Label(scrollable_frame, text="Subtítulos", bg=t["bg_surface"], fg=t["accent"], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, padx=6, pady=(8, 2))
        for i, s in enumerate(subtitle_streams):
            tags = s.get("tags") or {}
            title = tags.get("title") or f"Sub {i + 1}"
            lang = tags.get("language", "und")
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_: actualizar_estado_hardsub())
            sub_vars.append((var, s))
            ModernCheckbutton(
                scrollable_frame,
                text=f"{title} ({lang})",
                variable=var,
                bg=t["bg_surface"],
                fg=t["fg_primary"],
                activeforeground=t["fg_primary"],
                selectcolor=t["bg_input"],
                accent=t["accent"],
                border=t["border_strong"],
            ).pack(anchor=tk.W, padx=8, pady=2)

        dialog.after(50, _actualizar_scroll_combos)

        right = tk.Frame(body, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        tk.Label(right, text="Versiones a generar", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W, padx=14, pady=(12, 8))
        tk.Frame(right, height=1, bg=t["border"]).pack(fill=tk.X, padx=14, pady=(0, 8))

        def refresh():
            lst.delete(0, tk.END)
            for i, combo in enumerate(combinaciones):
                suffix = " (Hardsub)" if combo.get("hardsub") else ""
                lst.insert(tk.END, f"{i + 1}. {combo['label']}{suffix}")

        def agregar(mostrar_alerta=True):
            aud_sel = [s for var, s in audio_vars if var.get()]
            sub_sel = [s for var, s in sub_vars if var.get()]
            if not aud_sel and not sub_sel:
                if mostrar_alerta:
                    messagebox.showwarning("Sin seleccion", "Selecciona al menos una pista", parent=dialog)
                return False

            audio_indices = [s["index"] for s in aud_sel]
            sub_indices = [s["index"] for s in sub_sel]
            audio_ids = [obtener_identificador_pista(s) for s in aud_sel]
            sub_ids = [obtener_identificador_pista(s) for s in sub_sel]

            audio_langs = [(s.get("tags") or {}).get("language", "und").upper() for s in aud_sel]
            sub_langs = [(s.get("tags") or {}).get("language", "und").upper() for s in sub_sel]

            parts = ["_".join(audio_langs)] if audio_langs else []
            if sub_langs:
                parts.append("sub" + "_".join(sub_langs))
            label = "_".join(parts) if parts else "VERSION"

            combinaciones.append(
                {
                    "audio_indices": audio_indices,
                    "sub_indices": sub_indices,
                    "audio_identifiers": audio_ids,
                    "sub_identifiers": sub_ids,
                    "label": label,
                    "hardsub": var_hardsub.get(),
                }
            )
            refresh()
            for var, _ in audio_vars:
                var.set(False)
            for var, _ in sub_vars:
                var.set(False)
            var_hardsub.set(False)
            return True

        def quitar():
            sel = lst.curselection()
            if sel:
                del combinaciones[sel[0]]
                refresh()

        bt = tk.Frame(right, bg=t["bg_surface"])
        bt.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(6, 12))
        tk.Button(bt, text="Agregar versión adicional", command=agregar, bg=t["btn_success"], fg="white").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(bt, text="Quitar", command=quitar, bg=t["btn_danger"], fg="white").pack(side=tk.LEFT)

        lst = tk.Listbox(
            right,
            font=("Consolas", 9),
            bg=t["bg_subtle"],
            fg=t["fg_primary"],
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
            highlightthickness=1,
            highlightbackground=t["border"],
            relief=tk.FLAT,
        )
        lst.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=14, pady=(0, 4))

        def aceptar():
            aud_sel = [s for var, s in audio_vars if var.get()]
            sub_sel = [s for var, s in sub_vars if var.get()]
            if aud_sel or sub_sel:
                agregar(mostrar_alerta=False)

            if not combinaciones:
                messagebox.showwarning("Sin pistas seleccionadas", "Selecciona al menos una pista de audio o subtítulo antes de aceptar.", parent=dialog)
                return

            resultado["ok"] = True
            resultado["combinaciones"] = list(combinaciones)
            resultado["aplicar_todos"] = apply_all.get()
            dialog.destroy()

        tk.Button(bottom, text="Aceptar", command=aceptar, bg="#2D9CDB", fg="white", width=14).pack(side=tk.LEFT, padx=6)
        tk.Button(bottom, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=14).pack(side=tk.LEFT, padx=6)

        def on_close():
            aud_sel = [s for var, s in audio_vars if var.get()]
            sub_sel = [s for var, s in sub_vars if var.get()]
            if not combinaciones and (aud_sel or sub_sel):
                if messagebox.askyesno(
                    "Aplicar selección",
                    "Has marcado pistas para este video.\n\n¿Deseas aplicar esta selección y procesarlo?",
                    parent=dialog
                ):
                    aceptar()
                    return
            elif combinaciones:
                if messagebox.askyesno(
                    "Procesar versiones",
                    f"Tienes {len(combinaciones)} versión(es) configurada(s).\n\n¿Deseas procesar estas versiones?",
                    parent=dialog
                ):
                    resultado["ok"] = True
                    resultado["combinaciones"] = list(combinaciones)
                    resultado["aplicar_todos"] = apply_all.get()
                    dialog.destroy()
                    return
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close)
        dialog.bind("<Return>", lambda e: aceptar() if (e.widget == dialog or not isinstance(e.widget, tk.Button)) else None)

        dialog.wait_window()
        if not resultado["ok"]:
            if self.cancelar_procesamiento or modo_previo:
                return resultado

            ans = messagebox.askyesnocancel(
                "Cancelar proceso",
                "¿Deseas cancelar todo el procesamiento?\n\n"
                "Sí: Cancela toda la cola de videos.\n"
                "No: Salta este archivo y continúa con el siguiente.\n"
                "Cancelar: Vuelve a la selección de pistas.",
                parent=self.root
            )
            if ans is True:
                self.cancelar_procesamiento = True
                self._clear_subgroups()
                resultado["ok"] = False
            elif ans is False:
                resultado["ok"] = False
            else:
                if self.cancelar_procesamiento:
                    return resultado
                return self._show_combination_selector(info, filename, subgrupo_label)
        return resultado

