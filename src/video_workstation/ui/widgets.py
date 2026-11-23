"""Custom Tkinter widgets for Video Workstation."""

import math
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont


class RoundedButton(tk.Canvas):
    """Canvas-backed button with rounded corners and hover/press feedback."""

    def __init__(
        self,
        master,
        text="",
        command=None,
        bg="#2D9CDB",
        fg="white",
        activebackground=None,
        activeforeground="white",
        relief=None,
        width=None,
        height=None,
        font=("Segoe UI", 9, "bold"),
        padx=10,
        pady=4,
        state=tk.NORMAL,
        cursor="hand2",
        disabled_bg="#E2E8F0",
        disabled_fg="#94A3B8",
        align="center",
        **kwargs,
    ):
        self.master = master
        self.text = text
        self.command = command
        self.bg_color = bg
        self.fg_color = fg
        self.disabled_bg = disabled_bg
        self.disabled_fg = disabled_fg
        self.align = align
        self.active_bg = activebackground if activebackground else self._adjust_brightness(bg, -15)
        self.active_fg = activeforeground
        self.font = font
        self.state = state
        self.padx = padx
        self.pady = pady
        self.fixed_width = width is not None

        f_obj = tkfont.Font(font=self.font)
        text_w = f_obj.measure(text)
        text_h = f_obj.metrics("linespace")

        if height is not None:
            self.height = height
        else:
            self.height = text_h + 2 * pady + 6

        if width is not None:
            if width <= 40:
                self.width = max(text_w + 2 * padx, width * 8)
            else:
                self.width = width
        else:
            self.width = text_w + 2 * padx + 12

        parent_bg = "#F3F7FF"
        if master:
            try:
                bg_val = master.cget("bg")
                if bg_val:
                    parent_bg = bg_val
            except Exception:
                try:
                    bg_val = master.cget("background")
                    if bg_val:
                        parent_bg = bg_val
                except Exception:
                    try:
                        style_name = master.cget("style")
                        if style_name:
                            style = ttk.Style()
                            bg_val = style.lookup(style_name, "background")
                            if bg_val:
                                parent_bg = bg_val
                    except Exception:
                        pass

        for opt in (
            "activebackground",
            "activeforeground",
            "relief",
            "compound",
            "overrelief",
            "repeatdelay",
            "repeatinterval",
            "takefocus",
            "text",
            "command",
        ):
            kwargs.pop(opt, None)

        super().__init__(
            master,
            bg=parent_bg,
            bd=0,
            highlightthickness=0,
            width=self.width,
            height=self.height,
            cursor=cursor if state == tk.NORMAL else "",
            **kwargs,
        )

        self.rect_id = None
        self.text_id = None
        self.pressed = False

        self.draw_button()

        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)

    def _adjust_brightness(self, hex_color, percent):
        try:
            if not hex_color.startswith("#") or len(hex_color) != 7:
                return hex_color
            r = max(0, min(255, int(hex_color[1:3], 16) + percent))
            g = max(0, min(255, int(hex_color[3:5], 16) + percent))
            b = max(0, min(255, int(hex_color[5:7], 16) + percent))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def get_rounded_rect_points(self, x1, y1, x2, y2, r):
        points = []
        steps = 8
        for i in range(steps + 1):
            theta = -math.pi / 2 + (math.pi / 2) * (i / steps)
            points.append(x2 - r + r * math.cos(theta))
            points.append(y1 + r + r * math.sin(theta))
        for i in range(steps + 1):
            theta = 0 + (math.pi / 2) * (i / steps)
            points.append(x2 - r + r * math.cos(theta))
            points.append(y2 - r + r * math.sin(theta))
        for i in range(steps + 1):
            theta = math.pi / 2 + (math.pi / 2) * (i / steps)
            points.append(x1 + r + r * math.cos(theta))
            points.append(y2 - r + r * math.sin(theta))
        for i in range(steps + 1):
            theta = math.pi + (math.pi / 2) * (i / steps)
            points.append(x1 + r + r * math.cos(theta))
            points.append(y1 + r + r * math.sin(theta))
        return points

    def draw_button(self, fill_color=None):
        self.delete("all")
        if fill_color is None:
            fill_color = self.disabled_bg if self.state == tk.DISABLED else self.bg_color

        text_color = self.fg_color
        if self.state == tk.DISABLED:
            text_color = self.disabled_fg
            self.config(cursor="")
        else:
            self.config(cursor="hand2")

        r = min(6, self.width // 2, self.height // 2)
        points = self.get_rounded_rect_points(0, 0, self.width, self.height, r)
        self.rect_id = self.create_polygon(points, fill=fill_color, outline="", smooth=False)
        if self.align == "left":
            self.text_id = self.create_text(
                self.padx + 4,
                self.height / 2,
                text=self.text,
                fill=text_color,
                font=self.font,
                anchor=tk.W,
            )
        else:
            self.text_id = self.create_text(
                self.width / 2,
                self.height / 2,
                text=self.text,
                fill=text_color,
                font=self.font,
                justify=tk.CENTER,
            )

    def config(self, cnf=None, **kw):
        if cnf is not None:
            kw.update(cnf)

        redraw = False
        if "width" in kw:
            new_w = kw.pop("width")
            if new_w is not None:
                f_obj = tkfont.Font(font=self.font)
                text_w = f_obj.measure(self.text)
                if new_w <= 40:
                    self.width = max(text_w + 2 * self.padx + 12, new_w * 8)
                else:
                    self.width = max(text_w + 2 * self.padx, new_w)
                self.fixed_width = True
                super().config(width=self.width)
                redraw = True
        if "height" in kw:
            new_h = kw.pop("height")
            if new_h is not None:
                self.height = new_h
                super().config(height=self.height)
                redraw = True
        if "state" in kw:
            self.state = kw.pop("state")
            redraw = True
        if "text" in kw:
            self.text = kw.pop("text")
            if not self.fixed_width:
                f_obj = tkfont.Font(font=self.font)
                self.width = f_obj.measure(self.text) + 2 * self.padx + 12
                super().config(width=self.width)
            redraw = True
        if "command" in kw:
            self.command = kw.pop("command")
        if "bg" in kw or "background" in kw:
            self.bg_color = kw.pop("bg") if "bg" in kw else kw.pop("background")
            self.active_bg = self._adjust_brightness(self.bg_color, -15)
            redraw = True
        if "fg" in kw or "foreground" in kw:
            self.fg_color = kw.pop("fg") if "fg" in kw else kw.pop("foreground")
            redraw = True
        if "disabled_bg" in kw:
            self.disabled_bg = kw.pop("disabled_bg")
            redraw = True
        if "disabled_fg" in kw:
            self.disabled_fg = kw.pop("disabled_fg")
            redraw = True
        if "parent_bg" in kw:
            super().config(bg=kw.pop("parent_bg"))

        kw.pop("activebackground", None)
        kw.pop("activeforeground", None)
        kw.pop("relief", None)
        kw.pop("compound", None)

        if kw:
            super().config(**kw)

        if redraw:
            self.draw_button()

    def configure(self, cnf=None, **kw):
        self.config(cnf, **kw)

    def cget(self, option):
        if option == "state":
            return self.state
        if option in ("bg", "background"):
            return self.bg_color
        if option in ("fg", "foreground"):
            return self.fg_color
        if option == "text":
            return self.text
        return super().cget(option)

    def __getitem__(self, item):
        return self.cget(item)

    def on_enter(self, event):
        if self.state == tk.NORMAL:
            self.draw_button(self.active_bg)

    def on_leave(self, event):
        if self.state == tk.NORMAL:
            self.draw_button(self.bg_color)
            self.pressed = False

    def on_press(self, event):
        if self.state == tk.NORMAL:
            self.pressed = True
            self.draw_button(self._adjust_brightness(self.bg_color, -30))

    def on_release(self, event):
        if self.state == tk.NORMAL and self.pressed:
            self.pressed = False
            self.draw_button(self.active_bg)
            if self.command:
                self.command()


class ModernCheckbutton(tk.Canvas):
    """Canvas-backed rounded checkbox with theme and hover support."""

    def __init__(
        self,
        master,
        text="",
        variable=None,
        command=None,
        bg="#FFFFFF",
        fg="#475569",
        activebackground=None,
        activeforeground="#0F172A",
        selectcolor="#F1F5F9",
        accent="#2563EB",
        border="#CBD5E1",
        disabled_fg="#94A3B8",
        state=tk.NORMAL,
        font=("Segoe UI", 9),
        cursor="hand2",
        **kwargs,
    ):
        self.text = text
        self.variable = variable if variable is not None else tk.BooleanVar(value=False)
        self.command = command
        self.bg_color = bg
        self.fg_color = fg
        self.active_fg = activeforeground
        self.box_bg = selectcolor
        self.accent_color = accent
        self.border_color = border
        self.disabled_fg = disabled_fg
        self.state = state
        self.font = font
        self.hovered = False

        f_obj = tkfont.Font(font=self.font)
        text_w = f_obj.measure(text)
        text_h = f_obj.metrics("linespace")
        self.box_size = 16
        self.height = max(22, text_h + 4)
        self.width = self.box_size + 8 + text_w + 4

        super().__init__(
            master,
            width=self.width,
            height=self.height,
            bg=self.bg_color,
            highlightthickness=0,
            bd=0,
            cursor=cursor if self.state == tk.NORMAL else "arrow",
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_toggle)
        self._trace_id = self.variable.trace_add("write", lambda *_: self._draw())
        self.bind("<Destroy>", self._on_destroy)
        self._draw()

    def _on_destroy(self, event):
        if event.widget == self and self._trace_id:
            try:
                self.variable.trace_remove("write", self._trace_id)
            except Exception:
                pass
            self._trace_id = None

    def _draw_rounded_box(self, x1, y1, x2, y2, r, fill, outline, width=1.5):
        pts = [
            x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1,
            x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2,
            x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2,
            x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1,
        ]
        self.create_polygon(pts, smooth=True, fill=fill, outline=outline, width=width)

    def _draw(self):
        self.delete("all")
        checked = bool(self.variable.get())
        cy = self.height / 2
        bx1 = 1
        by1 = cy - self.box_size / 2
        bx2 = bx1 + self.box_size
        by2 = by1 + self.box_size

        disabled = self.state == tk.DISABLED
        if checked:
            fill_box = self.border_color if disabled else self.accent_color
            self._draw_rounded_box(bx1, by1, bx2, by2, 4, fill=fill_box, outline=fill_box, width=1)
            # Crisp checkmark inside the 16x16 box
            self.create_line(
                bx1 + 4, cy,
                bx1 + 7, cy + 3.2,
                bx1 + 12, cy - 3.2,
                fill="#FFFFFF",
                width=2,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )
        else:
            outline = self.border_color if disabled else (self.accent_color if self.hovered else self.border_color)
            self._draw_rounded_box(bx1, by1, bx2, by2, 4, fill=self.box_bg, outline=outline, width=1.5)

        if disabled:
            txt_color = self.disabled_fg
        else:
            txt_color = self.active_fg if (self.hovered or checked) else self.fg_color
        self.create_text(
            bx2 + 8,
            cy,
            text=self.text,
            fill=txt_color,
            font=self.font,
            anchor=tk.W,
        )

    def _on_enter(self, _event):
        if self.state == tk.NORMAL:
            self.hovered = True
            self._draw()

    def _on_leave(self, _event):
        self.hovered = False
        self._draw()

    def _on_toggle(self, _event):
        if self.state != tk.NORMAL:
            return
        self.variable.set(not bool(self.variable.get()))
        if self.command:
            self.command()

    def config(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        if "bg" in kw:
            self.bg_color = kw.pop("bg")
            super().config(bg=self.bg_color)
        if "background" in kw:
            self.bg_color = kw.pop("background")
            super().config(bg=self.bg_color)
        if "fg" in kw:
            self.fg_color = kw.pop("fg")
        if "foreground" in kw:
            self.fg_color = kw.pop("foreground")
        if "activeforeground" in kw:
            self.active_fg = kw.pop("activeforeground")
        kw.pop("activebackground", None)
        if "selectcolor" in kw:
            self.box_bg = kw.pop("selectcolor")
        if "accent" in kw:
            self.accent_color = kw.pop("accent")
        if "border" in kw:
            self.border_color = kw.pop("border")
        if "disabled_fg" in kw:
            self.disabled_fg = kw.pop("disabled_fg")
        if "state" in kw:
            self.state = kw.pop("state")
            super().config(cursor="hand2" if self.state == tk.NORMAL else "arrow")
        if kw:
            super().config(**kw)
        self._draw()

    def configure(self, cnf=None, **kw):
        self.config(cnf, **kw)


def center_window(window, width=None, height=None, parent=None):
    """
    Center a Tk window or Toplevel dialog on screen or over its parent window.
    Ensures titlebar and bottom action buttons remain fully visible on screen.
    Eliminates corner flash by keeping the window hidden until geometry is applied.
    """
    try:
        window.withdraw()
    except Exception:
        pass

    window.update_idletasks()

    w = int(width or window.winfo_width())
    if w <= 1:
        w = int(window.winfo_reqwidth())
    h = int(height or window.winfo_height())
    if h <= 1:
        h = int(window.winfo_reqheight())

    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()

    if parent and hasattr(parent, "winfo_ismapped") and parent.winfo_ismapped() and parent.winfo_width() > 100:
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
    else:
        x = (sw - w) // 2
        y = (sh - 48 - (h + 56)) // 2

    # Clamp bounds to screen so the title bar and bottom buttons are always reachable
    if x < 0:
        x = 0
    elif x + w > sw:
        x = max(0, sw - w)

    if y < 0:
        y = 0
    elif y + h > sh - 48:
        y = max(0, sh - 48 - h)

    window.geometry(f"{w}x{h}+{x}+{y}")

    try:
        window.deiconify()
    except Exception:
        pass

