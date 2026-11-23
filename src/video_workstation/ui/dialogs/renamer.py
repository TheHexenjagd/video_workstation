"""Batch regex and metadata-driven file renamer dialog."""

import json
import os
import re
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from video_workstation.ui.theme import get_theme
from video_workstation.ui.widgets import (
    ModernCheckbutton,
    RoundedButton,
    attach_treeview_column_dividers,
    center_window,
)


class RenamerDialogMixin:
    """Mixin providing the batch file renamer dialog and execution."""

    def _get_file_attributes(self, filepath):
        info = self._ffprobe_info(filepath)
        attrs = {
            "resolution": "unknown",
            "codec_v": "unknown",
            "codec_a": "unknown"
        }
        if info and "streams" in info:
            video_stream = next((s for s in info["streams"] if s.get("codec_type") == "video"), {})
            attrs["codec_v"] = video_stream.get("codec_name", "unknown")
            try:
                width = int(video_stream.get("width", 0))
                height = int(video_stream.get("height", 0))
                if height >= 2160 or width >= 3840:
                    attrs["resolution"] = "2160p"
                elif height >= 1080 or width >= 1920:
                    attrs["resolution"] = "1080p"
                elif height >= 720 or width >= 1280:
                    attrs["resolution"] = "720p"
                elif height >= 480 or width >= 854:
                    attrs["resolution"] = "480p"
                elif height > 0:
                    attrs["resolution"] = f"{height}p"
            except (ValueError, TypeError):
                pass
            
            audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
            if audio_streams:
                attrs["codec_a"] = audio_streams[0].get("codec_name", "unknown")
            else:
                attrs["codec_a"] = "none"
        return attrs

    def open_renamer(self):
        archivos = list(self.lista.get(0, tk.END))
        if not archivos:
            messagebox.showerror("Error", "Agrega al menos un video a la cola principal antes de renombrar.", parent=self.root)
            return

        # Declarar variables al inicio para uso en closures y bindings
        patron_var = tk.StringVar(value="{num} - {name}")
        inicio_var = tk.StringVar(value="1")
        digitos_var = tk.StringVar(value="2")
        buscar_var = tk.StringVar()
        reemplazar_var = tk.StringVar()
        usar_regex_var = tk.BooleanVar(value=True)

        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title("Renombrar Archivos")
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
        tk.Label(hdr_txt, text="Renombrar Archivos de la Cola", font=("Segoe UI", 11, "bold"), fg=t["fg_primary"], bg=t["bg_surface"]).pack(anchor=tk.W)
        tk.Label(hdr_txt, text="Configura un patrón de nombre para renombrar todos los archivos de la lista principal.", font=("Segoe UI", 9), fg=t["fg_muted"], bg=t["bg_surface"]).pack(anchor=tk.W, pady=(2, 0))

        content = tk.Frame(dialog, bg=t["bg_app"], padx=16)
        content.pack(fill=tk.BOTH, expand=True)

        left_col = tk.Frame(content, bg=t["bg_app"])
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        right_col = tk.Frame(content, bg=t["bg_app"])
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(8, 0))

        config_card = tk.Frame(left_col, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        config_card.pack(fill=tk.X, pady=(0, 10))

        cfg_hdr = tk.Frame(config_card, bg=t["bg_surface"])
        cfg_hdr.pack(fill=tk.X, padx=14, pady=(10, 6))
        tk.Label(cfg_hdr, text="Configuración del Patrón", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W)
        tk.Frame(config_card, height=1, bg=t["border"]).pack(fill=tk.X, padx=14, pady=(0, 10))

        cfg_body = tk.Frame(config_card, bg=t["bg_surface"])
        cfg_body.pack(fill=tk.X, padx=14, pady=(0, 12))

        # Fila de Presets
        row_presets = tk.Frame(cfg_body, bg=t["bg_surface"])
        row_presets.pack(fill=tk.X, pady=4)
        tk.Label(row_presets, text="Ajuste predefinido:", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(side=tk.LEFT, padx=(0, 6))

        PRESET_RENAME_TEMPLATES = {
            "Numeración Simple (01.mp4, 02.mp4...)": {
                "patron": "{num}", "buscar": "", "reemplazar": "", "regex": False
            },
            "Numeración + Nombre (01 - Nombre.mp4...)": {
                "patron": "{num} - {name}", "buscar": "", "reemplazar": "", "regex": False
            },
            "Extraer Capítulo (Capitulo 261 - Nombre -> 261 Nombre.mp4)": {
                "patron": "{name}", "buscar": r"Capitulo (\d+) - (.*)", "reemplazar": r"\1 \2", "regex": True
            },
            "Extraer Número de Episodio (01x03, s01e01, E09 -> 03.mp4...)": {
                "patron": "{name}", "buscar": r".*(?:s\d+e|\d+x|\b[eE]\s*|\bEp\s*|\bCapitulo\s*)(\d+).*", "reemplazar": r"\1", "regex": True
            }
        }

        try:
            custom_rename_presets = json.loads(self.config_ini.get("Options", "rename_presets", fallback="{}"))
        except Exception:
            custom_rename_presets = {}

        def obtener_todos_presets():
            todos = dict(PRESET_RENAME_TEMPLATES)
            todos.update(custom_rename_presets)
            return todos

        cb_presets = ttk.Combobox(row_presets, values=list(obtener_todos_presets().keys()), state="readonly", width=62)
        cb_presets.pack(side=tk.LEFT, padx=(0, 10))

        def on_rename_preset_selected(*_):
            sel = cb_presets.get()
            todos = obtener_todos_presets()
            if sel in todos:
                data = todos[sel]
                patron_var.set(data["patron"])
                buscar_var.set(data["buscar"])
                reemplazar_var.set(data["reemplazar"])
                usar_regex_var.set(data["regex"])

        cb_presets.bind("<<ComboboxSelected>>", on_rename_preset_selected)

        def guardar_preset_actual():
            nombre = simpledialog.askstring("Guardar Preset", "Ingresa un nombre para el preset:", parent=dialog)
            if not nombre:
                return
            nombre = nombre.strip()
            if not nombre:
                return
            if nombre in PRESET_RENAME_TEMPLATES:
                messagebox.showerror("Error", "No puedes sobrescribir los presets predefinidos del sistema.", parent=dialog)
                return
            
            try:
                curr = json.loads(self.config_ini.get("Options", "rename_presets", fallback="{}"))
            except Exception:
                curr = {}
            
            curr[nombre] = {
                "patron": patron_var.get(),
                "buscar": buscar_var.get(),
                "reemplazar": reemplazar_var.get(),
                "regex": usar_regex_var.get()
            }
            
            if "Options" not in self.config_ini:
                self.config_ini["Options"] = {}
            self.config_ini["Options"]["rename_presets"] = json.dumps(curr)
            self._save_config()
            
            nonlocal custom_rename_presets
            custom_rename_presets = curr
            
            cb_presets["values"] = list(obtener_todos_presets().keys())
            cb_presets.set(nombre)
            messagebox.showinfo("Guardado", f"Preset '{nombre}' guardado con éxito.", parent=dialog)

        def eliminar_preset_seleccionado():
            sel = cb_presets.get()
            if not sel:
                return
            if sel in PRESET_RENAME_TEMPLATES:
                messagebox.showerror("Error", "No puedes eliminar los presets predefinidos del sistema.", parent=dialog)
                return
            
            if messagebox.askyesno("Eliminar Preset", f"¿Estás seguro de que deseas eliminar el preset '{sel}'?", parent=dialog):
                try:
                    curr = json.loads(self.config_ini.get("Options", "rename_presets", fallback="{}"))
                except Exception:
                    curr = {}
                
                if sel in curr:
                    del curr[sel]
                    
                if "Options" not in self.config_ini:
                    self.config_ini["Options"] = {}
                self.config_ini["Options"]["rename_presets"] = json.dumps(curr)
                self._save_config()
                
                nonlocal custom_rename_presets
                custom_rename_presets = curr
                
                cb_presets["values"] = list(obtener_todos_presets().keys())
                cb_presets.set("")
                messagebox.showinfo("Eliminado", f"Preset '{sel}' eliminado con éxito.", parent=dialog)

        RoundedButton(row_presets, text="Guardar actual", command=guardar_preset_actual, bg=t["btn_success"], fg="#FFFFFF", font=("Segoe UI", 8, "bold"), width=110, height=26).pack(side=tk.LEFT, padx=3)
        RoundedButton(row_presets, text="Eliminar", command=eliminar_preset_seleccionado, bg=t["btn_danger"], fg="#FFFFFF", font=("Segoe UI", 8, "bold"), width=75, height=26).pack(side=tk.LEFT, padx=3)

        row_patron = tk.Frame(cfg_body, bg=t["bg_surface"])
        row_patron.pack(fill=tk.X, pady=4)
        tk.Label(row_patron, text="Patrón de nombre:", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(side=tk.LEFT, padx=(0, 6))

        entry_patron = tk.Entry(row_patron, textvariable=patron_var, font=("Consolas", 10), bg=t["bg_input"], fg=t["fg_primary"], insertbackground=t["fg_primary"], highlightthickness=1, highlightbackground=t["border"], relief=tk.FLAT)
        entry_patron.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        row_opts = tk.Frame(cfg_body, bg=t["bg_surface"])
        row_opts.pack(fill=tk.X, pady=4)

        tk.Label(row_opts, text="Inicio de número:", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(side=tk.LEFT, padx=(0, 4))
        sp_inicio = tk.Spinbox(row_opts, from_=0, to=999999, textvariable=inicio_var, width=6, font=("Segoe UI", 9), bg=t["bg_input"], fg=t["fg_primary"], buttonbackground=t["bg_subtle"], highlightthickness=1, highlightbackground=t["border"], relief=tk.FLAT)
        sp_inicio.pack(side=tk.LEFT, padx=(0, 15))

        tk.Label(row_opts, text="Dígitos de relleno:", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(side=tk.LEFT, padx=(0, 4))
        sp_digitos = tk.Spinbox(row_opts, from_=1, to=10, textvariable=digitos_var, width=4, font=("Segoe UI", 9), bg=t["bg_input"], fg=t["fg_primary"], buttonbackground=t["bg_subtle"], highlightthickness=1, highlightbackground=t["border"], relief=tk.FLAT)
        sp_digitos.pack(side=tk.LEFT, padx=(0, 15))

        row_reemplazo = tk.Frame(cfg_body, bg=t["bg_surface"])
        row_reemplazo.pack(fill=tk.X, pady=4)

        tk.Label(row_reemplazo, text="Buscar:", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(side=tk.LEFT, padx=(0, 4))
        entry_buscar = tk.Entry(row_reemplazo, textvariable=buscar_var, font=("Consolas", 10), bg=t["bg_input"], fg=t["fg_primary"], insertbackground=t["fg_primary"], highlightthickness=1, highlightbackground=t["border"], relief=tk.FLAT, width=22)
        entry_buscar.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(row_reemplazo, text="Reemplazar con:", font=("Segoe UI", 9, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(side=tk.LEFT, padx=(0, 4))
        entry_reemplazar = tk.Entry(row_reemplazo, textvariable=reemplazar_var, font=("Consolas", 10), bg=t["bg_input"], fg=t["fg_primary"], insertbackground=t["fg_primary"], highlightthickness=1, highlightbackground=t["border"], relief=tk.FLAT, width=22)
        entry_reemplazar.pack(side=tk.LEFT, padx=(0, 12))

        chk_regex = ModernCheckbutton(row_reemplazo, text="Usar Regex", variable=usar_regex_var, bg=t["bg_surface"], fg=t["fg_primary"], activeforeground=t["fg_primary"], selectcolor=t["bg_input"], accent=t["accent"], border=t["border_strong"], font=("Segoe UI", 9, "bold"))
        chk_regex.pack(side=tk.LEFT)

        row_helpers = tk.Frame(cfg_body, bg=t["bg_surface"])
        row_helpers.pack(fill=tk.X, pady=(6, 0))
        tk.Label(row_helpers, text="Insertar variable:", font=("Segoe UI", 8, "bold"), bg=t["bg_surface"], fg=t["fg_muted"]).pack(side=tk.LEFT, padx=(0, 6))

        def insertar_variable(var_name):
            pos = entry_patron.index(tk.INSERT)
            entry_patron.insert(pos, var_name)
            entry_patron.focus_set()

        for var_tag in ("{name}", "{num}", "{parent}"):
            btn_h = RoundedButton(
                row_helpers,
                text=var_tag,
                command=lambda v=var_tag: insertar_variable(v),
                bg=t["accent_soft"],
                fg=t["accent"],
                activebackground=t["accent"],
                activeforeground=t["accent_fg"],
                font=("Consolas", 8, "bold"),
                width=68,
                height=22,
            )
            btn_h.pack(side=tk.LEFT, padx=3)

        preview_card = tk.Frame(left_col, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"])
        preview_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        prev_hdr = tk.Frame(preview_card, bg=t["bg_surface"])
        prev_hdr.pack(fill=tk.X, padx=14, pady=(10, 6))
        tk.Label(prev_hdr, text="Vista Previa de Renombrado", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W)
        tk.Frame(preview_card, height=1, bg=t["border"]).pack(fill=tk.X, padx=14, pady=(0, 10))

        help_card = tk.Frame(right_col, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"], width=340)
        help_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        help_card.pack_propagate(False)

        help_hdr = tk.Frame(help_card, bg=t["bg_surface"])
        help_hdr.pack(fill=tk.X, padx=14, pady=(10, 6))
        tk.Label(help_hdr, text="Guía de Uso y Ejemplos", font=("Segoe UI", 10, "bold"), bg=t["bg_surface"], fg=t["fg_primary"]).pack(anchor=tk.W)
        tk.Frame(help_card, height=1, bg=t["border"]).pack(fill=tk.X, padx=14, pady=(0, 10))

        help_text = (
            "Variables del Patrón:\n"
            "• {name}: Nombre original del archivo (modificado por Buscar/Reemplazar si se usa).\n"
            "• {num}: Número secuencial.\n"
            "• {parent}: Nombre de la carpeta contenedora del video.\n\n"
            "Buscar y Reemplazar:\n"
            "Útil para reestructurar nombres. Soporta Regex y grupos de captura como \\1, \\2 o $1, $2.\n\n"
            "Ejemplo de reestructuración:\n"
            "Original: \"Capitulo 261 - No estás gritando.mp4\"\n"
            "Deseado: \"261 No estás gritando.mp4\"\n"
            "1. Patrón: {name}\n"
            "2. Buscar: Capitulo (\\d+) - (.*)\n"
            "3. Reemplazar con: \\1 \\2\n"
            "4. Usar Regex: Marcado\n\n"
            "Ejemplo de numeración simple:\n"
            "Original: \"Mi_Video.mp4\"\n"
            "Deseado: \"01.mp4\"\n"
            "1. Patrón: {num}\n"
            "2. Configura Inicio (1) y Dígitos (2)."
        )

        lbl_help = tk.Label(help_card, text=help_text, font=("Segoe UI", 9), bg=t["bg_surface"], fg=t["fg_secondary"], justify=tk.LEFT, anchor=tk.NW, wraplength=310)
        lbl_help.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))

        tree_container = tk.Frame(preview_card, bg=t["bg_surface"], highlightthickness=1, highlightbackground=t["border"], highlightcolor=t["border"])
        tree_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))

        style = ttk.Style()
        style.layout("Renamer.Treeview", [("Renamer.Treeview.treearea", {"sticky": "nswe"})])
        style.configure(
            "Renamer.Treeview",
            background=t["bg_surface"],
            foreground=t["fg_primary"],
            fieldbackground=t["bg_surface"],
            rowheight=26,
            borderwidth=0,
            focusthickness=0,
            font=("Segoe UI", 9),
        )
        style.map("Renamer.Treeview", background=[("selected", t["tree_sel_bg"])], foreground=[("selected", t["tree_sel_fg"])])
        style.configure(
            "Renamer.Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=t["heading_bg"],
            foreground=t["heading_fg"],
            relief="flat",
        )
        style.map(
            "Renamer.Treeview.Heading",
            background=[("active", t["bg_input"]), ("pressed", t["bg_input"])],
            foreground=[("active", t["fg_primary"]), ("pressed", t["fg_primary"])],
        )

        tree = ttk.Treeview(tree_container, columns=("original", "nuevo", "status"), show="headings", style="Renamer.Treeview", takefocus=False)
        tree.bind("<FocusIn>", lambda e: dialog.focus_set())
        tree.heading("original", text="Nombre Actual")
        tree.heading("nuevo", text="Nombre Nuevo Propuesto")
        tree.heading("status", text="Estado / Alerta")

        tree.column("original", width=320, anchor="w")
        tree.column("nuevo", width=340, anchor="w")
        tree.column("status", width=170, anchor="w")

        attach_treeview_column_dividers(
            tree,
            lambda: get_theme(self.theme_var.get())["border_strong"],
        )

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=tree.yview, style="Vertical.TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.config(yscrollcommand=scrollbar.set)

        tree.tag_configure("ok", foreground=t["success"])
        tree.tag_configure("conflict", foreground=t["warning"], font=("Segoe UI", 9, "bold"))
        tree.tag_configure("error", foreground=t["danger"], font=("Segoe UI", 9, "bold"))
        tree.tag_configure("no_change", foreground=t["fg_muted"])

        item_to_path = {}

        def _es_nombre_valido(nombre):
            if not nombre.strip():
                return False
            invalidos = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
            return not any(c in nombre for c in invalidos)

        def actualizar_preview(*_):
            for item in tree.get_children():
                tree.delete(item)
            item_to_path.clear()

            patron = patron_var.get()
            try:
                inicio = int(inicio_var.get())
            except ValueError:
                inicio = 1
            try:
                digitos = int(digitos_var.get())
            except ValueError:
                digitos = 2

            from collections import Counter
            new_paths = []
            parsed_results = []

            for idx, filepath in enumerate(archivos):
                num_val = inicio + idx
                num_str = f"{num_val:0{digitos}d}"

                parent_dir = os.path.dirname(filepath)
                name_with_ext = os.path.basename(filepath)
                stem, ext = os.path.splitext(name_with_ext)
                parent_name = os.path.basename(parent_dir)

                # Apply Buscar y Reemplazar on original stem
                buscar = buscar_var.get()
                reemplazar = reemplazar_var.get()
                if buscar:
                    if usar_regex_var.get():
                        try:
                            import re
                            py_reemplazar = reemplazar
                            py_reemplazar = re.sub(r'\$(\d+)', lambda m: f'\\g<{m.group(1)}>', py_reemplazar)
                            py_reemplazar = re.sub(r'\\(\d+)', lambda m: f'\\g<{m.group(1)}>', py_reemplazar)
                            stem = re.sub(buscar, py_reemplazar, stem, flags=re.IGNORECASE)
                        except Exception:
                            # In case of invalid regex, keep stem unchanged
                            pass
                    else:
                        stem = stem.replace(buscar, reemplazar)

                resolution = "unknown"
                codec_v = "unknown"
                codec_a = "unknown"

                if any(tag in patron for tag in ("{resolution}", "{codec_v}", "{codec_a}")):
                    attrs = self._get_file_attributes(filepath)
                    resolution = attrs["resolution"]
                    codec_v = attrs["codec_v"]
                    codec_a = attrs["codec_a"]

                resolved = patron
                resolved = resolved.replace("{name}", stem)
                resolved = resolved.replace("{num}", num_str)
                resolved = resolved.replace("{parent}", parent_name)
                resolved = resolved.replace("{resolution}", resolution)
                resolved = resolved.replace("{codec_v}", codec_v)
                resolved = resolved.replace("{codec_a}", codec_a)

                new_name = resolved + ext
                new_path = os.path.join(parent_dir, new_name)
                new_paths.append(os.path.normcase(os.path.normpath(new_path)))
                parsed_results.append((filepath, new_name, new_path))

            path_counts = Counter(new_paths)

            for filepath, new_name, new_path in parsed_results:
                orig_norm = os.path.normcase(os.path.normpath(filepath))
                dest_norm = os.path.normcase(os.path.normpath(new_path))

                if not _es_nombre_valido(new_name):
                    status = "Error: Caracteres inválidos"
                    tag = "error"
                elif path_counts[dest_norm] > 1:
                    status = "Conflicto: Duplicado en cola"
                    tag = "conflict"
                elif os.path.exists(new_path) and dest_norm != orig_norm:
                    status = "Conflicto: Ya existe en disco"
                    tag = "conflict"
                elif dest_norm == orig_norm:
                    status = "Sin cambios"
                    tag = "no_change"
                else:
                    status = "Listo"
                    tag = "ok"

                item_id = tree.insert("", tk.END, values=(os.path.basename(filepath), new_name, status), tags=(tag,))
                item_to_path[item_id] = filepath

        patron_var.trace_add("write", actualizar_preview)
        inicio_var.trace_add("write", actualizar_preview)
        digitos_var.trace_add("write", actualizar_preview)
        buscar_var.trace_add("write", actualizar_preview)
        reemplazar_var.trace_add("write", actualizar_preview)
        usar_regex_var.trace_add("write", actualizar_preview)
        
        actualizar_preview()

        btm = tk.Frame(dialog, bg=t["bg_app"])
        btm.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 16))

        btn_container = tk.Frame(btm, bg=t["bg_app"])
        btn_container.pack(anchor=tk.CENTER)

        RoundedButton(btn_container, text="Aplicar Renombrado", command=lambda: self._execute_renaming(dialog, archivos, tree, item_to_path), bg=t["btn_success"], fg="#FFFFFF", font=("Segoe UI", 9, "bold"), width=160, height=34).pack(side=tk.LEFT, padx=10)
        RoundedButton(btn_container, text="Cancelar", command=dialog.destroy, bg=t["btn_secondary_bg"], fg=t["btn_secondary_fg"], font=("Segoe UI", 9, "bold"), width=110, height=34).pack(side=tk.LEFT, padx=10)

        center_window(dialog, 1260, 740, self.root)

    def _execute_renaming(self, dialog, archivos, tree, item_to_path=None):
        if not archivos:
            messagebox.showwarning("Sin archivos", "No hay archivos en la cola para renombrar.", parent=dialog)
            return

        has_errors = False
        has_conflicts = False
        items = tree.get_children()

        for item_id in items:
            vals = tree.item(item_id, "values")
            status = vals[2]
            if "Error" in status:
                has_errors = True
            elif "Conflicto" in status:
                has_conflicts = True

        if has_errors:
            messagebox.showerror("Error de Validación", "Por favor, corrija los errores de caracteres inválidos antes de aplicar el renombrado.", parent=dialog)
            return

        if has_conflicts:
            confirm = messagebox.askyesno(
                "Confirmar Conflictos",
                "Hay conflictos detectados (nombres duplicados o archivos existentes en disco).\n"
                "¿Desea continuar de todos modos? Algunos archivos podrían no renombrarse o sobrescribirse.",
                parent=dialog,
                icon="warning"
            )
            if not confirm:
                return
        else:
            confirm = messagebox.askyesno(
                "Confirmar Renombrado",
                f"¿Desea proceder a renombrar los {len(archivos)} archivos de la cola?",
                parent=dialog
            )
            if not confirm:
                return

        self._clear_log_and_progress("Renombrando archivos...")
        self._log_message("===== INICIO RENOMBRADO DE ARCHIVOS =====")
        ok_count = 0
        fail_count = 0
        mapping_renombres = {}

        for item_id in items:
            _, proposed_name, status = tree.item(item_id, "values")
            original_path = item_to_path.get(item_id) if item_to_path else _

            if status == "Sin cambios":
                mapping_renombres[original_path] = original_path
                continue

            parent_dir = os.path.dirname(original_path)
            new_path = os.path.join(parent_dir, proposed_name)

            if os.path.normcase(os.path.normpath(original_path)) == os.path.normcase(os.path.normpath(new_path)):
                mapping_renombres[original_path] = original_path
                continue

            try:
                os.rename(original_path, new_path)
                self._invalidate_file_cache(original_path)
                self._log_message(f"Renombrado con éxito:\n  De: {original_path}\n  A: {new_path}")
                self._record_activity("exito", os.path.basename(new_path), "Renombrado", f"Antes: {os.path.basename(original_path)}")
                mapping_renombres[original_path] = new_path
                ok_count += 1
            except Exception as exc:
                self._log_message(f"Error al renombrar {os.path.basename(original_path)}: {exc}")
                self._record_activity("error", os.path.basename(original_path), "Renombrado", str(exc))
                mapping_renombres[original_path] = original_path
                fail_count += 1

        self.progress["value"] = 100
        self.progress_label.config(text=f"Renombrado completado | Éxitos: {ok_count} | Fallos: {fail_count}")

        all_items = list(self.lista.get(0, tk.END))
        self.lista.delete(0, tk.END)
        for path in all_items:
            new_val = mapping_renombres.get(path, path)
            self.lista.insert(tk.END, os.path.normpath(new_val))
        self._update_queue_counters()

        self._log_message("===== FIN RENOMBRADO DE ARCHIVOS =====")
        self._log_message(f"Renombrados con éxito: {ok_count} | Errores: {fail_count}")

        dialog.destroy()
        messagebox.showinfo("Renombrado Finalizado", f"Se han renombrado {ok_count} archivos correctamente.\nErrores: {fail_count}")

