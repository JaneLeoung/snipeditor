import io
import os
import sys
import ctypes
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
from PIL import Image, ImageTk, ImageGrab, ImageDraw, ImageFont

APP_TITLE = 'Snip Annotate Tool'
RECT_WIDTH_DEFAULT = 3
MAX_PREVIEW_SIZE = (1400, 900)
TEXT_SIZE_DEFAULT = 24
RECT_COLOR_DEFAULT = '#ff0000'
TEXT_COLOR_DEFAULT = '#ff0000'
BRUSH_COLOR_DEFAULT = '#ff0000'
BRUSH_WIDTH_DEFAULT = 5

BG_DARK = '#1f1f1f'
PANEL_DARK = '#2a2a2a'
PANEL_MID = '#333333'
TEXT_LIGHT = '#f2f2f2'

ACCENT_BLUE = '#3a6ea5'
ACCENT_BROWN = '#6c5a3a'
ACCENT_GREEN = '#2d6a2d'
ACCENT_GREY = '#555555'


def enable_high_dpi_mode():
    if not sys.platform.startswith('win'):
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def get_virtual_screen_bounds():
    if not sys.platform.startswith('win'):
        return 0, 0, 0, 0

    user32 = ctypes.windll.user32
    left = user32.GetSystemMetrics(76)
    top = user32.GetSystemMetrics(77)
    width = user32.GetSystemMetrics(78)
    height = user32.GetSystemMetrics(79)

    return left, top, width, height


def get_windows_display_scale_percent():
    if not sys.platform.startswith('win'):
        return 100

    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        dc = user32.GetDC(0)

        if not dc:
            return 100

        try:
            logical_w = user32.GetSystemMetrics(0)
            physical_w = gdi32.GetDeviceCaps(dc, 118)

            if logical_w > 0 and physical_w > 0:
                return max(100, int(round((physical_w / logical_w) * 100)))
        finally:
            user32.ReleaseDC(0, dc)

    except Exception:
        pass

    return 100


def get_preview_bounds(root):
    try:
        screen_w = max(900, root.winfo_screenwidth() - 80)
        screen_h = max(600, root.winfo_screenheight() - 180)
        return min(MAX_PREVIEW_SIZE[0], screen_w), min(MAX_PREVIEW_SIZE[1], screen_h)
    except Exception:
        return MAX_PREVIEW_SIZE


def fit_size(width, height, max_w, max_h):
    scale = min(max_w / width, max_h / height, 1.0)
    return int(width * scale), int(height * scale), scale


def get_font(size=24):
    candidates = [
        'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass

    return ImageFont.load_default()


def copy_image_to_clipboard(img):
    if not sys.platform.startswith('win'):
        return False, 'Clipboard copy is currently Windows-only.'

    try:
        import win32clipboard

        output = io.BytesIO()
        img.convert('RGB').save(output, 'BMP')
        data = output.getvalue()[14:]
        output.close()

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        finally:
            win32clipboard.CloseClipboard()

        return True, 'Copied to clipboard.'

    except Exception as e:
        return False, f'Failed to copy to clipboard: {e}'


class SnipOverlay(tk.Toplevel):
    def __init__(self, parent, screenshot, on_done):
        super().__init__(parent)

        self.parent = parent
        self.screenshot = screenshot
        self.on_done = on_done

        self.start_x = 0
        self.start_y = 0
        self.rect_id = None

        self.virtual_left, self.virtual_top, self.virtual_width, self.virtual_height = get_virtual_screen_bounds()

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.geometry(
            f'{self.virtual_width}x{self.virtual_height}+{self.virtual_left}+{self.virtual_top}'
        )

        self.canvas = tk.Canvas(self, highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)

        self.photo = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo)

        self.canvas.bind('<ButtonPress-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)

        self.bind('<Escape>', lambda e: self.cancel())
        self.bind('<Control-q>', lambda e: self.parent.destroy())

        self.update()
        self.lift()
        self.focus_force()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y

        if self.rect_id:
            self.canvas.delete(self.rect_id)

        self.rect_id = self.canvas.create_rectangle(
            self.start_x,
            self.start_y,
            self.start_x,
            self.start_y,
            outline='red',
            width=2
        )

    def on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(
                self.rect_id,
                self.start_x,
                self.start_y,
                event.x,
                event.y
            )

    def on_release(self, event):
        x1, y1 = self.start_x, self.start_y
        x2, y2 = event.x, event.y

        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))

        if right - left < 5 or bottom - top < 5:
            self.cancel()
            return

        overlay_w = max(1, self.winfo_width())
        overlay_h = max(1, self.winfo_height())

        scale_x = self.screenshot.width / overlay_w
        scale_y = self.screenshot.height / overlay_h

        crop_left = max(0, int(left * scale_x))
        crop_top = max(0, int(top * scale_y))
        crop_right = min(self.screenshot.width, int(right * scale_x))
        crop_bottom = min(self.screenshot.height, int(bottom * scale_y))

        if crop_right - crop_left < 5 or crop_bottom - crop_top < 5:
            self.cancel()
            return

        cropped = self.screenshot.crop(
            (crop_left, crop_top, crop_right, crop_bottom)
        )

        self.destroy()
        self.on_done(cropped)

    def cancel(self):
        self.destroy()
        self.on_done(None)


class Editor(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_DARK)

        self.master = master
        self.master.title(APP_TITLE)
        self.pack(fill='both', expand=True)

        self.image = None
        self.preview_image = None
        self.preview_photo = None
        self.scale = 1.0

        self.actions = []
        self.current_rect_start = None
        self.current_rect_id = None

        self.rect_color = RECT_COLOR_DEFAULT
        self.rect_width = RECT_WIDTH_DEFAULT
        self.text_color = TEXT_COLOR_DEFAULT
        self.brush_color = BRUSH_COLOR_DEFAULT
        self.brush_width = BRUSH_WIDTH_DEFAULT
        self.current_brush_points = []
        self.current_brush_preview_ids = []

        self.text_size = tk.IntVar(value=TEXT_SIZE_DEFAULT)
        self.auto_display_scale = tk.BooleanVar(value=True)
        self.display_scale_percent = tk.IntVar(value=get_windows_display_scale_percent())
        self.status_text = tk.StringVar(value='Ready')
        self.mode = tk.StringVar(value='rect')

        self.active_text_entry = None
        self.active_text_window_id = None
        self.active_text_position = None
        self.active_text_var = None

        self.build_ui()

        self.master.bind('<Escape>', lambda e: self.master.destroy())
        self.master.bind('<Control-q>', lambda e: self.master.destroy())
        self.master.bind('<Control-n>', lambda e: self.start_snip())

        self.master.geometry('1400x950')
        self.apply_display_scale()

        # Auto start snip after app opens.
        self.master.after_idle(self.start_snip)

    def build_ui(self):
        self.master.configure(bg=BG_DARK)
        self.configure(bg=BG_DARK)

        bottom = tk.Frame(self, bg=BG_DARK)
        bottom.pack(side='bottom', fill='x', padx=10, pady=(0, 10))

        body = tk.Frame(self, bg=BG_DARK)
        body.pack(side='top', fill='both', expand=True, padx=10, pady=10)

        image_frame = tk.Frame(
            body,
            bg=PANEL_DARK,
            bd=0,
            highlightthickness=1,
            highlightbackground='#444444'
        )
        image_frame.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(
            image_frame,
            bg='#202020',
            highlightthickness=0,
            cursor='crosshair',
            bd=0,
            relief='flat'
        )
        self.canvas.pack(fill='both', expand=True, padx=6, pady=6)

        self.canvas.bind('<ButtonPress-1>', self.canvas_press)
        self.canvas.bind('<B1-Motion>', self.canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.canvas_release)

        bottom = tk.Frame(self, bg=BG_DARK)
        bottom.pack(fill='x', padx=10, pady=(0, 10))

        toolbar = tk.Frame(
            bottom,
            bg=PANEL_DARK,
            bd=0,
            highlightthickness=1,
            highlightbackground='#444444'
        )
        toolbar.pack(fill='x', pady=(0, 8))

        left = tk.Frame(toolbar, bg=PANEL_DARK)
        left.pack(side='left', padx=8, pady=8)

        right = tk.Frame(toolbar, bg=PANEL_DARK)
        right.pack(side='right', padx=8, pady=8)

        self.make_tool_button(left, '✂ New', self.start_snip, ACCENT_GREY).pack(side='left', padx=4)
        self.make_tool_button(left, '🖼 Open', self.load_image, ACCENT_GREY).pack(side='left', padx=4)
        self.make_tool_button(left, '✏ Text', lambda: self.set_mode('text'), ACCENT_BLUE).pack(side='left', padx=4)
        self.make_tool_button(left, '⬜ Select', lambda: self.set_mode('rect'), ACCENT_BROWN).pack(side='left', padx=4)
        self.make_tool_button(left, '🖌 Brush', lambda: self.set_mode('brush'), ACCENT_BLUE).pack(side='left', padx=4)
        self.make_tool_button(left, '↩ Undo', self.undo_last, ACCENT_GREY).pack(side='left', padx=4)
        self.make_tool_button(left, '🗑 Discard', self.clear_all, ACCENT_GREY).pack(side='left', padx=4)

        self.make_tool_button(right, '📋', self.copy_and_exit, ACCENT_GREEN).pack(side='left', padx=4)
        self.make_tool_button(right, '💾', self.save_png, ACCENT_GREY).pack(side='left', padx=4)

        options = tk.Frame(
            bottom,
            bg=PANEL_DARK,
            bd=0,
            highlightthickness=1,
            highlightbackground='#444444'
        )
        options.pack(fill='x')

        self.mode_label = tk.Label(
            options,
            text='Current Mode: Box',
            bg=PANEL_DARK,
            fg=TEXT_LIGHT,
            font=('Segoe UI', 10)
        )
        self.mode_label.pack(side='left', padx=(12, 14), pady=10)

        tk.Label(
            options,
            text='Box Width',
            bg=PANEL_DARK,
            fg=TEXT_LIGHT,
            font=('Segoe UI', 10)
        ).pack(side='left', padx=(0, 6))

        rect_spin = tk.Spinbox(
            options,
            from_=1,
            to=12,
            width=4,
            command=lambda: self.update_rect_width(rect_spin.get())
        )
        rect_spin.delete(0, 'end')
        rect_spin.insert(0, str(self.rect_width))
        rect_spin.pack(side='left', padx=(0, 14), pady=8)
        rect_spin.bind('<KeyRelease>', lambda e: self.update_rect_width(rect_spin.get()))

        tk.Label(
            options,
            text='Text Size',
            bg=PANEL_DARK,
            fg=TEXT_LIGHT,
            font=('Segoe UI', 10)
        ).pack(side='left', padx=(0, 6))

        text_spin = tk.Spinbox(
            options,
            from_=10,
            to=96,
            textvariable=self.text_size,
            width=4,
            command=self.on_text_size_change
        )
        text_spin.pack(side='left', padx=(0, 14), pady=8)
        text_spin.bind('<KeyRelease>', lambda e: self.on_text_size_change())

        self.make_tool_button(options, 'Box Color', self.pick_rect_color, ACCENT_GREY, compact=True).pack(side='left', padx=(0, 6))
        self.make_tool_button(options, 'Text Color', self.pick_text_color, ACCENT_GREY, compact=True).pack(side='left', padx=(0, 14))
        tk.Label(
            options,
            text='Brush Width',
            bg=PANEL_DARK,
            fg=TEXT_LIGHT,
            font=('Segoe UI', 10)
        ).pack(side='left', padx=(0, 6))

        brush_spin = tk.Spinbox(
            options,
            from_=1,
            to=40,
            width=4
        )
        brush_spin.delete(0, 'end')
        brush_spin.insert(0, str(self.brush_width))
        brush_spin.pack(side='left', padx=(0, 14), pady=8)

        brush_spin.config(command=lambda: self.update_brush_width(brush_spin.get()))
        brush_spin.bind('<KeyRelease>', lambda e: self.update_brush_width(brush_spin.get()))

        # ---- Brush Color ----
        self.make_tool_button(
            options,
            'Brush Color',
            self.pick_brush_color,
            ACCENT_GREY,
            compact=True
        ).pack(side='left', padx=(0, 14))

        auto_dpi = tk.Checkbutton(
            options,
            text='Auto DPI',
            variable=self.auto_display_scale,
            command=self.apply_display_scale,
            bg=PANEL_DARK,
            fg=TEXT_LIGHT,
            activebackground=PANEL_DARK,
            activeforeground=TEXT_LIGHT,
            selectcolor=PANEL_MID,
            font=('Segoe UI', 10)
        )
        auto_dpi.pack(side='left', padx=(0, 8))

        tk.Label(
            options,
            text='Scale %',
            bg=PANEL_DARK,
            fg=TEXT_LIGHT,
            font=('Segoe UI', 10)
        ).pack(side='left', padx=(0, 6))

        dpi_spin = tk.Spinbox(
            options,
            from_=50,
            to=300,
            textvariable=self.display_scale_percent,
            width=4,
            command=self.apply_display_scale
        )
        dpi_spin.pack(side='left', padx=(0, 10), pady=8)
        dpi_spin.bind('<KeyRelease>', lambda e: self.apply_display_scale())

        self.status_label = tk.Label(
            bottom,
            textvariable=self.status_text,
            anchor='w',
            bg=BG_DARK,
            fg='#d8d8d8',
            font=('Segoe UI', 10)
        )
        self.status_label.pack(fill='x', pady=(8, 0))

    def make_tool_button(self, parent, text, command, bg, compact=False):
        font_size = 10 if compact else 11
        padx = 10 if compact else 14
        pady = 7 if compact else 9

        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg='white',
            activebackground=bg,
            activeforeground='white',
            relief='flat',
            bd=0,
            padx=padx,
            pady=pady,
            font=('Segoe UI', font_size, 'bold'),
            cursor='hand2'
        )

    def apply_display_scale(self):
        try:
            detected = get_windows_display_scale_percent()

            if self.auto_display_scale.get():
                value = detected
            else:
                value = max(50, min(300, int(self.display_scale_percent.get())))

            self.display_scale_percent.set(value)

            if sys.platform.startswith('win'):
                try:
                    self.master.tk.call('tk', 'scaling', 1.0)
                except Exception:
                    pass

            self.refresh_canvas()
            self.status_text.set(f'Display scale set to {value}%.')

        except Exception:
            self.refresh_canvas()

    def set_mode(self, mode):
        if self.current_brush_preview_ids:
            for i in self.current_brush_preview_ids:
                try:
                    self.canvas.delete(i)
                except:
                    pass
            self.current_brush_preview_ids = []
            self.current_brush_points = []
        self.mode.set(mode)
        if mode == 'rect':
            self.mode_label.configure(text='Current Mode: Box')
            self.status_text.set('Box mode: drag on image to add a box.')
        elif mode == 'text':
            self.mode_label.configure(text='Current Mode: Text')
            self.status_text.set('Text mode: click on image and type directly.')
        elif mode == 'brush':
            self.mode_label.configure(text='Current Mode: Brush')
            self.status_text.set('Brush mode: drag to draw.')

    def update_rect_width(self, value):
        try:
            self.rect_width = max(1, int(value))
            self.refresh_canvas()
            self.status_text.set(f'Box width set to {self.rect_width}.')
        except Exception:
            pass

    def on_text_size_change(self):
        try:
            self.text_size.set(max(10, int(self.text_size.get())))
        except Exception:
            self.text_size.set(TEXT_SIZE_DEFAULT)

        self.refresh_canvas()
        self.update_active_text_entry_style()
        self.status_text.set(f'Text size set to {self.text_size.get()}.')

    def start_snip(self):
        self.cancel_active_text_entry(commit=False)
        self.master.withdraw()
        self.master.after(500, self._take_snip)

    def _take_snip(self):
        try:
            screenshot = ImageGrab.grab(all_screens=True)
        except Exception:
            screenshot = ImageGrab.grab()

        self.master.deiconify()
        self.master.lift()

        SnipOverlay(self.master, screenshot, self.set_image)

    def set_image(self, image):
        if image is None:
            self.status_text.set('Screenshot cancelled.')
            return

        self.image = image.convert('RGB')
        self.actions = []
        self.current_rect_start = None
        self.current_rect_id = None
        self.current_brush_points = []
        self.current_brush_preview_ids = []

        self.cancel_active_text_entry(commit=False)
        self.refresh_canvas()

        self.status_text.set('New screenshot loaded.')

    def load_image(self):
        path = filedialog.askopenfilename(
            title='Open image',
            filetypes=[
                ('Image files', '*.png *.jpg *.jpeg *.bmp *.webp'),
                ('All files', '*.*')
            ]
        )

        if not path:
            return

        try:
            self.image = Image.open(path).convert('RGB')
            self.actions = []
            self.current_rect_start = None
            self.current_rect_id = None

            self.cancel_active_text_entry(commit=False)
            self.refresh_canvas()

            self.status_text.set(f'Opened {os.path.basename(path)}.')

        except Exception as e:
            messagebox.showerror('Open image failed', str(e))

    def refresh_canvas(self):
        if self.image is None:
            self.canvas.delete('all')
            return

        rendered = self.render_result_image(include_edit_preview=True)

        max_w, max_h = get_preview_bounds(self.master)
        pw, ph, scale = fit_size(rendered.width, rendered.height, max_w, max_h)

        self.scale = scale

        if scale != 1:
            self.preview_image = rendered.resize((pw, ph), Image.LANCZOS)
        else:
            self.preview_image = rendered

        self.preview_photo = ImageTk.PhotoImage(self.preview_image)

        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor='nw', image=self.preview_photo)

        self.canvas.config(
            scrollregion=(0, 0, self.preview_image.width, self.preview_image.height)
        )

        self.redraw_active_text_entry()

    def render_result_image(self, include_edit_preview=False):
        img = self.image.copy()
        draw = ImageDraw.Draw(img)

        for action in self.actions:
            if action['type'] == 'rect':
                draw.rectangle(
                    action['bbox'],
                    outline=action['color'],
                    width=action['width']
                )

            elif action['type'] == 'text':
                font = get_font(size=action['size'])
                draw.multiline_text(
                    action['position'],
                    action['text'],
                    fill=action['color'],
                    font=font,
                    spacing=6
                )
            elif action['type'] == 'brush':
                points = action['points']

                if len(points) >= 2:
                    draw.line(
                        points,
                        fill=action['color'],
                        width=action['width'],
                        joint='curve'
                    )

        if include_edit_preview and self.active_text_position and self.active_text_var is not None:
            preview = self.active_text_var.get()

            if preview:
                font = get_font(size=max(10, int(self.text_size.get())))
                draw.multiline_text(
                    self.active_text_position,
                    preview,
                    fill=self.text_color,
                    font=font,
                    spacing=6
                )

        return img

    def canvas_press(self, event):
        if self.image is None:
            return

        if self.mode.get() == 'rect':
            img_x, img_y = self.preview_to_image_coords(event.x, event.y)

            if img_x is None:
                return

            self.current_rect_start = (img_x, img_y)
            self.current_rect_id = self.canvas.create_rectangle(
                event.x,
                event.y,
                event.x,
                event.y,
                outline=self.rect_color,
                width=self.rect_width
            )

        elif self.mode.get() == 'brush':
            img_x, img_y = self.preview_to_image_coords(event.x, event.y)

            if img_x is None:
                return

            self.current_brush_points = [(img_x, img_y)]
            self.current_brush_preview_ids = []

    def canvas_drag(self, event):
        if self.image is None:
            return

        if self.mode.get() == 'rect':
            if self.current_rect_id is not None and self.current_rect_start is not None:
                start_x = int(self.current_rect_start[0] * self.scale)
                start_y = int(self.current_rect_start[1] * self.scale)

                self.canvas.coords(
                    self.current_rect_id,
                    start_x,
                    start_y,
                    event.x,
                    event.y
                )

        elif self.mode.get() == 'brush':
            img_x, img_y = self.preview_to_image_coords(event.x, event.y)

            if img_x is None or not self.current_brush_points:
                return

            self.current_brush_points.append((img_x, img_y))

            # Draw smoother preview using the last 3 points
            points = self.current_brush_points[-3:]

            coords = []
            for px, py in points:
                coords.extend([
                    int(px * self.scale),
                    int(py * self.scale)
                ])

            line_id = self.canvas.create_line(
                *coords,
                fill=self.brush_color,
                width=max(1, int(self.brush_width * self.scale)),
                capstyle='round',
                smooth=True
            )

            self.current_brush_preview_ids.append(line_id)

    def canvas_release(self, event):
        if self.image is None:
            return

        if self.mode.get() == 'rect':
            self.finish_rectangle(event)

        elif self.mode.get() == 'text':
            self.start_inline_text(event)

        elif self.mode.get() == 'brush':
            self.finish_brush()

    def finish_rectangle(self, event):
        if self.current_rect_start is None:
            return

        x1, y1 = self.current_rect_start
        x2, y2 = self.preview_to_image_coords(event.x, event.y)

        if x2 is None:
            self.current_rect_start = None
            self.current_rect_id = None
            self.refresh_canvas()
            return

        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))

        if right - left >= 4 and bottom - top >= 4:
            self.actions.append({
                'type': 'rect',
                'bbox': (left, top, right, bottom),
                'color': self.rect_color,
                'width': self.rect_width,
            })

            self.refresh_canvas()
            self.status_text.set('Box added.')

        else:
            self.refresh_canvas()

        self.current_rect_start = None
        self.current_rect_id = None

    def finish_brush(self):
        if len(self.current_brush_points) >= 2:
            self.actions.append({
                'type': 'brush',
                'points': self.current_brush_points[:],
                'color': self.brush_color,
                'width': self.brush_width,
            })
            self.status_text.set('Brush stroke added.')

        self.current_brush_points = []

        for item_id in self.current_brush_preview_ids:
            try:
                self.canvas.delete(item_id)
            except Exception:
                pass

        self.current_brush_preview_ids = []

        self.refresh_canvas()

    def start_inline_text(self, event):
        img_x, img_y = self.preview_to_image_coords(event.x, event.y)

        if img_x is None:
            return

        self.cancel_active_text_entry(commit=True)

        self.active_text_position = (img_x, img_y)
        self.active_text_var = tk.StringVar(value='')
        self.active_text_var.trace_add('write', self.on_active_text_change)

        self.active_text_entry = tk.Entry(
            self.canvas,
            textvariable=self.active_text_var,
            bd=1,
            relief='solid',
            fg=self.text_color,
            insertbackground=self.text_color,
            bg='#ffffff',
        )

        self.update_active_text_entry_style()

        preview_x = int(img_x * self.scale)
        preview_y = int(img_y * self.scale)

        self.active_text_window_id = self.canvas.create_window(
            preview_x,
            preview_y,
            anchor='nw',
            window=self.active_text_entry,
            width=260
        )

        self.active_text_entry.bind('<Return>', lambda e: self.commit_active_text())
        self.active_text_entry.bind('<Escape>', lambda e: self.cancel_active_text_entry(commit=False))
        self.active_text_entry.bind('<FocusOut>', lambda e: self.commit_active_text())

        self.active_text_entry.focus_set()

        self.status_text.set('Typing on image, Enter to finish, Esc to cancel.')

    def update_active_text_entry_style(self):
        if self.active_text_entry is not None:
            font_size = max(10, int(self.text_size.get()))
            self.active_text_entry.configure(
                font=('Arial', font_size),
                fg=self.text_color,
                insertbackground=self.text_color
            )

    def redraw_active_text_entry(self):
        if self.active_text_entry is None or self.active_text_position is None:
            return

        preview_x = int(self.active_text_position[0] * self.scale)
        preview_y = int(self.active_text_position[1] * self.scale)

        if self.active_text_window_id is not None:
            self.canvas.delete(self.active_text_window_id)

        self.active_text_window_id = self.canvas.create_window(
            preview_x,
            preview_y,
            anchor='nw',
            window=self.active_text_entry,
            width=260
        )

        self.active_text_entry.lift()

    def on_active_text_change(self, *_args):
        self.refresh_canvas()

    def commit_active_text(self):
        if self.active_text_entry is None or self.active_text_var is None or self.active_text_position is None:
            return

        text = self.active_text_var.get().strip()
        pos = self.active_text_position

        self.cancel_active_text_entry(commit=False)

        if not text:
            self.refresh_canvas()
            self.status_text.set('Empty text ignored.')
            return

        self.actions.append({
            'type': 'text',
            'position': pos,
            'text': text,
            'color': self.text_color,
            'size': max(10, int(self.text_size.get())),
        })

        self.refresh_canvas()
        self.status_text.set('Text added.')

    def cancel_active_text_entry(self, commit=False):
        if commit and self.active_text_entry is not None:
            self.commit_active_text()
            return

        if self.active_text_window_id is not None:
            try:
                self.canvas.delete(self.active_text_window_id)
            except Exception:
                pass

        if self.active_text_entry is not None:
            try:
                self.active_text_entry.destroy()
            except Exception:
                pass

        self.active_text_entry = None
        self.active_text_window_id = None
        self.active_text_position = None
        self.active_text_var = None

    def preview_to_image_coords(self, preview_x, preview_y):
        if self.image is None:
            return None, None

        img_w, img_h = self.image.size

        x = int(preview_x / self.scale)
        y = int(preview_y / self.scale)

        if x < 0 or y < 0 or x > img_w or y > img_h:
            return None, None

        return x, y

    def undo_last(self):
        self.cancel_active_text_entry(commit=False)

        if self.actions:
            last = self.actions.pop()
            self.refresh_canvas()
            self.status_text.set(f'Undid {last["type"]}.')
        else:
            self.status_text.set('Nothing to undo.')

    def clear_all(self):
        self.cancel_active_text_entry(commit=False)
        self.actions = []
        self.refresh_canvas()
        self.status_text.set('All annotations cleared.')

    def pick_rect_color(self):
        color = colorchooser.askcolor(
            color=self.rect_color,
            title='Pick rectangle color'
        )[1]

        if color:
            self.rect_color = color
            self.status_text.set('Box color updated.')

    def pick_text_color(self):
        color = colorchooser.askcolor(
            color=self.text_color,
            title='Pick text color'
        )[1]

        if color:
            self.text_color = color
            self.update_active_text_entry_style()
            self.refresh_canvas()
            self.status_text.set('Text color updated.')

    def update_brush_width(self, value):
        try:
            self.brush_width = max(1, int(value))
            self.status_text.set(f'Brush width set to {self.brush_width}.')
        except Exception:
            pass

    def pick_brush_color(self):
        color = colorchooser.askcolor(
            color=self.brush_color,
            title='Pick brush color'
        )[1]

        if color:
            self.brush_color = color
            self.status_text.set('Brush color updated.')

    def save_png(self):
        if self.image is None:
            return

        self.cancel_active_text_entry(commit=True)

        path = filedialog.asksaveasfilename(
            title='Save result',
            defaultextension='.png',
            filetypes=[('PNG image', '*.png')],
        )

        if not path:
            return

        try:
            self.render_result_image().save(path, format='PNG')
            self.status_text.set(f'Saved: {path}')
        except Exception as e:
            messagebox.showerror('Save failed', str(e))

    def copy_and_exit(self):
        if self.image is None:
            return

        self.cancel_active_text_entry(commit=True)

        img = self.render_result_image()
        ok, msg = copy_image_to_clipboard(img)

        self.status_text.set(msg)

        if ok:
            self.master.after(50, self.master.destroy)


def main():
    enable_high_dpi_mode()

    root = tk.Tk()
    root.tk.call('tk', 'scaling', 1.0)

    Editor(root)

    root.mainloop()


if __name__ == '__main__':
    main()