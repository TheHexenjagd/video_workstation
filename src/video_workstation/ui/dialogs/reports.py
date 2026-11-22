"""Pre-check, verification diagnostics, preset selector, about, and error summary dialogs."""

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from video_workstation import VERSION
from video_workstation.constants import PRESETS_AMD, PRESETS_NVIDIA, PRESETS_QSV
from video_workstation.ui.theme import get_theme


class ReportsDialogMixin:
    """Mixin providing verification, diagnostics, preset, about, and error dialogs."""

    def _show_precheck_report(self, resultados, tipo_proceso, archivos, callback_exito):
        dialog = tk.Toplevel(self.root)
        dialog.title("Reporte de Pre-verificacion - VW")
        dialog.geometry("820x600")
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)
        dialog.configure(bg="#F3F7FF")

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        header = tk.Frame(dialog, bg="#1A2536", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Pre-verificacion de Archivos",
            font=("Segoe UI", 14, "bold"),
            bg="#1A2536",
            fg="#FFFFFF"
        ).pack(anchor=tk.W, padx=20, pady=(10, 2))

        tk.Label(
            header,
            text="Se han detectado posibles problemas. Elige cómo deseas proceder con la cola de procesamiento.",
            font=("Segoe UI", 9),
            bg="#1A2536",
            fg="#B0C4DE"
        ).pack(anchor=tk.W, padx=20)

        num_errors = 0
        num_warnings = 0
        for r in resultados:
            if r["has_error"]:
                num_errors += len(r["errors"])
            if r["has_warning"]:
                num_warnings += len(r["warnings"])

        btm = tk.Frame(dialog, bg="#F3F7FF")
        btm.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(5, 15))

        def cmd_continuar():
            filtrados = [r["archivo"] for r in resultados if not r["has_error"]]
            dialog.destroy()

            con_errores = [r["archivo"] for r in resultados if r["has_error"]]
            if con_errores:
                self.root.after(0, lambda: self._move_to_skipped(con_errores))

            if filtrados:
                callback_exito(filtrados)
            else:
                messagebox.showwarning("Cola vacia", "No quedan archivos validos para procesar tras excluir los errores.")

        def cmd_omitir_problemas():
            filtrados = [r["archivo"] for r in resultados if not r["has_error"] and not r["has_warning"]]
            dialog.destroy()

            con_problemas = [r["archivo"] for r in resultados if r["has_error"] or r["has_warning"]]
            if con_problemas:
                self.root.after(0, lambda: self._move_to_skipped(con_problemas))

            if filtrados:
                callback_exito(filtrados)
            else:
                messagebox.showwarning("Cola vacia", "No quedan archivos limpios sin advertencias ni errores para procesar.")

        def cmd_cancelar():
            self._clear_subgroups()
            dialog.destroy()

        btn_cancelar = tk.Button(
            btm,
            text="Cancelar",
            command=cmd_cancelar,
            bg="#95A5A6",
            fg="white",
            activebackground="#7F8C8D",
            activeforeground="white",
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_cancelar.pack(side=tk.RIGHT, padx=5)

        if num_warnings > 0 or num_errors > 0:
            btn_omitir = tk.Button(
                btm,
                text="Omitir archivos con problemas",
                command=cmd_omitir_problemas,
                bg="#F2994A",
                fg="white",
                activebackground="#D35400",
                activeforeground="white",
                relief=tk.FLAT,
                padx=15,
                pady=6,
                cursor="hand2",
                font=("Segoe UI", 9, "bold")
            )
            btn_omitir.pack(side=tk.RIGHT, padx=5)

        archivos_sin_errores = [r for r in resultados if not r["has_error"]]
        if archivos_sin_errores:
            btn_continuar = tk.Button(
                btm,
                text="Agregar de todos modos",
                command=cmd_continuar,
                bg="#27AE60",
                fg="white",
                activebackground="#219653",
                activeforeground="white",
                relief=tk.FLAT,
                padx=15,
                pady=6,
                cursor="hand2",
                font=("Segoe UI", 9, "bold")
            )
            btn_continuar.pack(side=tk.RIGHT, padx=5)

        body = tk.Frame(dialog, bg="#F3F7FF", padx=20, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        text_frame = tk.Frame(body, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5ECF9")

        log_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            bg="#FFFFFF",
            fg="#1F2A44",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame, command=log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.config(yscrollcommand=scrollbar.set)

        log_text.tag_config("title", font=("Segoe UI", 10, "bold"), spacing1=8, spacing3=2)
        log_text.tag_config("error_lbl", font=("Segoe UI", 9, "bold"), foreground="#EB5757")
        log_text.tag_config("warn_lbl", font=("Segoe UI", 9, "bold"), foreground="#F2994A")
        log_text.tag_config("detail", font=("Segoe UI", 9), foreground="#4F4F4F", lmargin1=25, lmargin2=25, spacing3=4)

        for r in resultados:
            if not r["has_error"] and not r["has_warning"]:
                continue

            log_text.insert(tk.END, f"Archivo: {r['basename']}\n", "title")

            for err in r["errors"]:
                log_text.insert(tk.END, "  [ERROR] ", "error_lbl")
                log_text.insert(tk.END, f"{err}\n", "detail")

            for warn in r["warnings"]:
                log_text.insert(tk.END, "  [ADVERTENCIA] ", "warn_lbl")
                log_text.insert(tk.END, f"{warn}\n", "detail")

        log_text.config(state=tk.DISABLED)

        summary_text = f"Resumen: {num_errors} error(es) critico(s) y {num_warnings} advertencia(s) encontrada(s)."
        lbl_summary = tk.Label(body, text=summary_text, font=("Segoe UI", 9, "bold"), bg="#F3F7FF", fg="#1F2A44", anchor=tk.W)

        if num_errors > 0:
            lbl_err_note = tk.Label(
                body,
                text="* Los archivos con errores criticos no podran ser procesados y seran excluidos si decide continuar.",
                font=("Segoe UI", 8, "italic"),
                bg="#F3F7FF",
                fg="#EB5757",
                anchor=tk.W
            )

        lbl_legend = tk.Label(
            body,
            text="• Agregar de todos modos: Procesa todos los archivos (incluyendo los que tienen advertencias).\n"
                 "• Omitir archivos con problemas: Excluye los archivos con advertencias o errores y procesa el resto.",
            font=("Segoe UI", 9, "italic"),
            bg="#F3F7FF",
            fg="#4F4F4F",
            justify=tk.LEFT,
            anchor=tk.W
        )

        lbl_legend.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 10))
        if num_errors > 0:
            lbl_err_note.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        lbl_summary.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 5))

        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _show_verification_results(self, resultados):
        t = get_theme(self.theme_var.get())
        win = tk.Toplevel(self.root)
        win.title("Diagnóstico de la cola - VW")
        win.geometry("980x640")
        win.minsize(820, 520)
        win.transient(self.root)
        win.configure(bg=t["bg_app"])
        win._vw_themed = True

        win.update_idletasks()
        x = self.root.winfo_x() + max(0, (self.root.winfo_width() - 980) // 2)
        y = self.root.winfo_y() + max(0, (self.root.winfo_height() - 640) // 2)
        win.geometry(f"+{x}+{y}")

        saludables = [r for r in resultados if not r["has_error"] and not r["has_warning"]]
        advertencias = [r for r in resultados if r["has_warning"] and not r["has_error"]]
        errores = [r for r in resultados if r["has_error"]]

        shell = tk.Frame(win, bg=t["bg_app"])
        shell.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(shell, width=215, bg=t["bg_sidebar"])
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Frame(shell, width=1, bg=t["border"]).pack(side=tk.LEFT, fill=tk.Y)

        brand_row = tk.Frame(sidebar, bg=t["bg_sidebar"])
        brand_row.pack(fill=tk.X, padx=16, pady=(18, 14))
        tk.Label(brand_row, text="VW", font=("Segoe UI", 11, "bold"), bg=t["accent"], fg="#FFFFFF", padx=8, pady=2).pack(side=tk.LEFT)
        brand_txt = tk.Frame(brand_row, bg=t["bg_sidebar"])
        brand_txt.pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(brand_txt, text="Diagnóstico", font=("Segoe UI", 10, "bold"), bg=t["bg_sidebar"], fg=t["fg_primary"]).pack(anchor=tk.W)
        tk.Label(brand_txt, text="Integridad de cola", font=("Segoe UI", 8), bg=t["bg_sidebar"], fg=t["fg_muted"]).pack(anchor=tk.W)

        tk.Frame(sidebar, height=1, bg=t["border"]).pack(fill=tk.X, padx=16, pady=(0, 12))
        tk.Label(sidebar, text="FILTROS", font=("Segoe UI", 8, "bold"), bg=t["bg_sidebar"], fg=t["fg_muted"]).pack(anchor=tk.W, padx=18, pady=(0, 6))

        nav_btns = {}

        def _poblar_tabla(clave):
            for k, btn in nav_btns.items():
                activo = k == clave
                btn.config(
                    bg=t["accent"] if activo else t["bg_sidebar"],
                    fg="#FFFFFF" if activo else t["fg_secondary"],
                    parent_bg=t["bg_sidebar"],
                )

            titulos = {
                "todos": "Todos los archivos",
                "saludables": "Archivos saludables",
                "advertencias": "Archivos con advertencias",
                "errores": "Errores o inaccesibles",
            }
            lbl_titulo.config(text=titulos.get(clave, "Diagnóstico"))
            tree.delete(*tree.get_children())

            if clave in ("todos", "saludables"):
                for r in saludables:
                    tree.insert("", tk.END, values=("Saludable", r["basename"], r["archivo"]), tags=("exito",))
            if clave in ("todos", "advertencias"):
                for r in advertencias:
                    det = " | ".join(r["warnings"]) if r["warnings"] else r["archivo"]
                    tree.insert("", tk.END, values=("Advertencia", r["basename"], det), tags=("aviso",))
            if clave in ("todos", "errores"):
                for r in errores:
                    det = " | ".join(r["errors"]) if r["errors"] else r["archivo"]
                    tree.insert("", tk.END, values=("Error", r["basename"], det), tags=("error",))

        filtros = [
            ("todos", f"Todos ({len(resultados)})"),
            ("saludables", f"Saludables ({len(saludables)})"),
            ("advertencias", f"Advertencias ({len(advertencias)})"),
            ("errores", f"Errores ({len(errores)})"),
        ]
        for key, txt in filtros:
            b = tk.Button(
                sidebar,
                text=txt,
                command=lambda k=key: _poblar_tabla(k),
                bg=t["bg_sidebar"],
                fg=t["fg_secondary"],
                width=183,
                height=32,
                align="left",
                padx=12,
                font=("Segoe UI", 9, "bold"),
            )
            b.pack(padx=16, pady=2)
            nav_btns[key] = b

        side_btm = tk.Frame(sidebar, bg=t["bg_sidebar"])
        side_btm.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(8, 16))
        tk.Frame(side_btm, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 12))
        tk.Button(
            side_btm,
            text="Cerrar",
            command=win.destroy,
            bg=t["btn_primary"],
            fg="#FFFFFF",
            width=183,
            height=34,
            font=("Segoe UI", 9, "bold"),
        ).pack()

        content = tk.Frame(shell, bg=t["bg_app"])
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        topbar = tk.Frame(content, height=52, bg=t["bg_surface"])
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Frame(content, height=1, bg=t["border"]).pack(fill=tk.X)

        lbl_titulo = tk.Label(topbar, text="Todos los archivos", font=("Segoe UI", 11, "bold"), bg=t["bg_surface"], fg=t["fg_primary"])
        lbl_titulo.pack(side=tk.LEFT, padx=20)
        tk.Label(
            topbar,
            text=f"Saludables: {len(saludables)}  |  Advertencias: {len(advertencias)}  |  Errores: {len(errores)}",
            font=("Segoe UI", 9),
            bg=t["bg_surface"],
            fg=t["fg_muted"],
        ).pack(side=tk.RIGHT, padx=20)

        card = tk.Frame(content, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        card.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        tree_frame = tk.Frame(card, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"], highlightcolor=t["border"])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        tree = ttk.Treeview(tree_frame, columns=("estado", "archivo", "detalle"), show="headings", style="Activity.Treeview", takefocus=False)
        tree.bind("<FocusIn>", lambda e: win.focus_set())
        tree.heading("estado", text="Estado")
        tree.heading("archivo", text="Archivo")
        tree.heading("detalle", text="Ruta / Detalle")
        tree.column("estado", width=105, minwidth=95, anchor=tk.CENTER, stretch=False)
        tree.column("archivo", width=260, minwidth=160, anchor=tk.W, stretch=True)
        tree.column("detalle", width=360, minwidth=200, anchor=tk.W, stretch=True)

        tree.tag_configure("exito", foreground=t["success"], background=t["success_bg"])
        tree.tag_configure("aviso", foreground=t["warning"], background=t["warning_bg"])
        tree.tag_configure("error", foreground=t["danger"], background=t["danger_bg"])

        def _limpiar_sel(event):
            if event.widget is tree:
                if not tree.identify_row(event.y):
                    tree.selection_remove(tree.selection())
            elif tree.selection():
                tree.selection_remove(tree.selection())

        win.bind("<Button-1>", _limpiar_sel, add="+")

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scr = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview, style="Vertical.TScrollbar")
        scr.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scr.set)

        _poblar_tabla("todos")

    def change_preset(self):
        gpu_acel = self.gpu_acel_var.get()
        if gpu_acel == "nvidia":
            presets = PRESETS_NVIDIA
            gpu_name = "NVIDIA NVENC"
            orden_presets = ["lossless", "hq", "slow", "bd", "default", "medium", "llhq", "fast", "ll", "llhp", "hp"]
        elif gpu_acel == "intel":
            presets = PRESETS_QSV
            gpu_name = "Intel QSV"
            orden_presets = ["veryslow", "slow", "medium", "fast", "faster", "veryfast"]
        else:
            presets = PRESETS_AMD
            gpu_name = "AMD AMF"
            orden_presets = ["quality", "balanced", "speed"]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Preset - {gpu_name}")
        dialog.geometry("620x420")
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)

        tk.Label(dialog, text=f"Selecciona preset para {gpu_name}", font=("Segoe UI", 12, "bold")).pack(pady=10)

        options = []
        map_display = {}
        for key in orden_presets:
            if key not in presets:
                continue
            info = presets[key]
            disp = info["nombre"]
            options.append(disp)
            map_display[disp] = key

        current = self.preset_var.get()
        current = current if current in presets else obtener_preset_valido(current, gpu_acel)
        value = tk.StringVar(value=presets[current]["nombre"])

        cb = ttk.Combobox(dialog, values=options, state="readonly", textvariable=value, width=44)
        cb.pack(pady=8)

        info_lbl = tk.Label(dialog, text="", justify=tk.LEFT, wraplength=560, anchor=tk.W)
        info_lbl.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def refresh(*_):
            selected = map_display.get(value.get())
            if not selected:
                return
            p = presets[selected]
            info_lbl.config(text=f"Nombre: {p['nombre']}\nVelocidad: {p['velocidad']}\nCalidad: {p['calidad']}\n\n{p['descripcion']}")

        value.trace_add("write", refresh)
        refresh()

        def aceptar():
            selected = map_display.get(value.get())
            if selected:
                self.preset_var.set(selected)
            dialog.destroy()

        btm = tk.Frame(dialog)
        btm.pack(pady=10)
        tk.Button(btm, text="Aceptar", command=aceptar, bg="#2D9CDB", fg="white", width=12).pack(side=tk.LEFT, padx=6)
        tk.Button(btm, text="Cancelar", command=dialog.destroy, bg="#95A5A6", fg="white", width=12).pack(side=tk.LEFT, padx=6)

    def show_about(self):
        import webbrowser

        dialog = tk.Toplevel(self.root)
        dialog.title("Acerca de Video Workstation (VW)")
        dialog.geometry("560x350")
        dialog.resizable(False, False)
        dialog.configure(bg="#F3F7FF")
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        header_card = tk.Frame(dialog, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5ECF9", bd=0)
        header_card.pack(fill=tk.X, padx=18, pady=(14, 8))

        text_container = tk.Frame(header_card, bg="#FFFFFF")
        text_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=14, pady=10)

        t_act = get_theme(self.theme_var.get())
        tk.Label(
            text_container,
            text="VW",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg=t_act["accent"],
            padx=8,
            pady=2,
        ).pack(side=tk.LEFT)

        tk.Label(
            text_container,
            text="  Acerca de Video Workstation",
            font=("Segoe UI", 10, "bold"),
            fg="#1F2A44",
            bg="#FFFFFF"
        ).pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(
            header_card,
            text=f"v{VERSION}",
            font=("Segoe UI", 9, "bold"),
            bg="#FFFFFF",
            fg="#2D9CDB"
        ).pack(side=tk.RIGHT, padx=14, pady=10)

        content_card = tk.Frame(dialog, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5ECF9", bd=0)
        content_card.pack(fill=tk.BOTH, expand=True, padx=18, pady=(4, 10))

        content = tk.Frame(content_card, bg="#FFFFFF", padx=16, pady=12)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            content,
            text="Video Workstation",
            font=("Segoe UI", 12, "bold"),
            bg="#FFFFFF",
            fg="#1F2A44"
        ).pack(anchor=tk.W)

        desc = (
            "Video Workstation (VW) es una estación de trabajo para la optimización de flujos de trabajo de vídeo. "
            "Automatiza la multiplexación de audio/subtítulos (remux), la codificación acelerada por hardware "
            "(NVIDIA NVENC, Intel QSV, AMD AMF) con incrustado de subtítulos (hardsub), el renombrado masivo "
            "por lotes con expresiones regulares, la limpieza de metadatos in-place y la organización en rutas dinámicas."
        )
        tk.Label(
            content,
            text=desc,
            font=("Segoe UI", 9),
            bg="#FFFFFF",
            fg="#5C6B8A",
            justify=tk.LEFT,
            wraplength=460
        ).pack(anchor=tk.W, pady=(6, 10))

        tk.Frame(content, height=1, bg="#E5ECF9").pack(fill=tk.X, pady=(0, 10))

        info_frame = tk.Frame(content, bg="#FFFFFF")
        info_frame.pack(fill=tk.X)
        info_frame.columnconfigure(1, weight=1)

        tk.Label(
            info_frame,
            text="Desarrolladores:",
            font=("Segoe UI", 9, "bold"),
            bg="#FFFFFF",
            fg="#2B3A57"
        ).grid(row=0, column=0, sticky=tk.NW, pady=3)

        devs_subframe = tk.Frame(info_frame, bg="#FFFFFF")
        devs_subframe.grid(row=0, column=1, sticky=tk.W, padx=12, pady=3)

        dev1_lbl = tk.Label(
            devs_subframe,
            text="• Gabriel Giraldo Herrera (github.com/TheHexenjagd)",
            font=("Segoe UI", 9, "underline"),
            bg="#FFFFFF",
            fg="#2D9CDB",
            cursor="hand2"
        )
        dev1_lbl.pack(anchor=tk.W, pady=1)
        dev1_lbl.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/TheHexenjagd"))

        dev2_lbl = tk.Label(
            devs_subframe,
            text="• Jorge Iván Nieto Triviño (github.com/Gatozo)",
            font=("Segoe UI", 9, "underline"),
            bg="#FFFFFF",
            fg="#2D9CDB",
            cursor="hand2"
        )
        dev2_lbl.pack(anchor=tk.W, pady=1)
        dev2_lbl.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/Gatozo"))

        btn_close = tk.Button(
            dialog,
            text="Cerrar",
            command=dialog.destroy,
            bg="#2D9CDB",
            fg="white",
            activebackground="#2D9CDB",
            activeforeground="white",
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_close.pack(side=tk.BOTTOM, pady=(0, 12))

    def _show_error_summary(self, errores):
        dialog = tk.Toplevel(self.root)
        dialog.title("Resumen de Errores - VW")
        dialog.geometry("740x500")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.attributes('-disabled', True)
        dialog.bind("<Destroy>", lambda e: self.root.attributes('-disabled', False) if (e.widget == dialog and self.root.winfo_exists()) else None)
        dialog.configure(bg="#F3F7FF")

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        header = tk.Frame(dialog, bg="#1A2536", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Resumen de Errores de Procesamiento",
            font=("Segoe UI", 14, "bold"),
            bg="#1A2536",
            fg="#FFFFFF"
        ).pack(anchor=tk.W, padx=20, pady=(10, 2))

        tk.Label(
            header,
            text="Los siguientes problemas ocurrieron al procesar los archivos de la cola:",
            font=("Segoe UI", 9),
            bg="#1A2536",
            fg="#B0C4DE"
        ).pack(anchor=tk.W, padx=20)

        body = tk.Frame(dialog, bg="#F3F7FF", padx=20, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        text_frame = tk.Frame(body, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E5ECF9")
        text_frame.pack(fill=tk.BOTH, expand=True)

        log_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            bg="#FFFFFF",
            fg="#1F2A44",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame, command=log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.config(yscrollcommand=scrollbar.set)

        log_text.tag_config("file_title", font=("Segoe UI", 10, "bold"), spacing1=8, spacing3=2)
        log_text.tag_config("error_lbl", font=("Segoe UI", 9, "bold"), foreground="#EB5757")
        log_text.tag_config("detail", font=("Segoe UI", 9), foreground="#4F4F4F", lmargin1=25, lmargin2=25, spacing3=4)

        for archivo, err_desc in errores:
            basename = os.path.basename(archivo) if archivo != "General" else "General"
            log_text.insert(tk.END, f"Archivo: {basename}\n", "file_title")
            log_text.insert(tk.END, "  [ERROR] ", "error_lbl")
            log_text.insert(tk.END, f"{err_desc}\n", "detail")

        log_text.config(state=tk.DISABLED)

        btm = tk.Frame(dialog, bg="#F3F7FF")
        btm.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(5, 15))

        btn_cerrar = tk.Button(
            btm,
            text="Cerrar",
            command=dialog.destroy,
            bg="#2D9CDB",
            fg="white",
            activebackground="#2185C5",
            activeforeground="white",
            relief=tk.FLAT,
            padx=20,
            pady=6,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        btn_cerrar.pack(side=tk.RIGHT)

