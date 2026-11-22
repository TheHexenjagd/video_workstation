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
        **kwargs,
    ):
        self.master = master
        self.text = text
        self.command = command
        self.bg_color = bg
        self.fg_color = fg
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
            fill_color = "#E0E0E0" if self.state == tk.DISABLED else self.bg_color

        text_color = self.fg_color
        if self.state == tk.DISABLED:
            text_color = "#A0A0A0"
            self.config(cursor="")
        else:
            self.config(cursor="hand2")

        r = min(6, self.width // 2, self.height // 2)
        points = self.get_rounded_rect_points(0, 0, self.width, self.height, r)
        self.rect_id = self.create_polygon(points, fill=fill_color, outline="", smooth=False)
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
