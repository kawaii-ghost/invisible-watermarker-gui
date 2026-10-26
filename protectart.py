"""Tkinter front end for invisible-watermarker that used in ArtShield.

Run it from the repository root (the watermarking code is bundled in
third_party/invisible-watermarker/):
    python proteccart.py

Dependencies: numpy, pillow, pywavelets, and tkinter (bundled with Python;
some distros package it separately, e.g. python3-tkinter).
Optional: pillow-jxl-plugin (pip install pillow-jxl-plugin) to read and write
JPEG XL. Without it, the JXL option is hidden automatically.
"""
import contextlib
import io
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from PIL import Image

try:
    from PIL import ImageTk
except ImportError:  # preview is disabled if ImageTk is unavailable
    ImageTk = None

try:
    import pillow_jxl  # noqa: F401  (registers the JXL format with Pillow)
    HAS_JXL = True
except ImportError:
    HAS_JXL = False

HERE = os.path.dirname(os.path.abspath(__file__))
# The watermarking code is bundled under third_party/. Fall back to a
# `watermark/` folder next to this file (the original upstream src/ layout).
for _cand in (os.path.join(HERE, "third_party", "invisible-watermarker"), HERE):
    if os.path.isdir(os.path.join(_cand, "watermark")):
        sys.path.insert(0, _cand)
        break
from watermark.apply_watermark import apply_watermark, Filetype  # noqa: E402
# `watermark/__init__.py` adds the watermark/ folder to sys.path,
# so the import below is only valid after the line above.
from max_dct.max_dct_encoder import DecodeMaxDct  # noqa: E402

_EXTS = "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff" + (" *.jxl" if HAS_JXL else "")
IMG_TYPES = [("Images", _EXTS), ("All files", "*.*")]
FORMATS = {"PNG": "PNG", "JPEG 4:4:4": "JPEG"}
if HAS_JXL:
    FORMATS["JXL lossless"] = "JXL"
MAX_CHARS = 16


# ---------------------------------------------------------------- core
def validate_text(text):
    if not text or not text.isascii() or len(text) > MAX_CHARS:
        raise ValueError(f"Watermark text must be ASCII, 1-{MAX_CHARS} characters.")
    return text


def read_bits(path, nbits):
    arr = np.asarray(Image.open(path).convert("RGB"))
    return np.array(DecodeMaxDct(wm_length=nbits).decode_rgb(arr)).astype(int)


def bits_to_text(bits):
    return np.packbits(bits).tobytes().decode("ascii", "replace")


def bit_accuracy(path, text):
    expected = np.unpackbits(np.frombuffer(text.encode("ascii"), dtype=np.uint8))
    return float((read_bits(path, len(expected)) == expected).mean())


def unique_path(folder, base, ext):
    out, n = os.path.join(folder, base + ext), 1
    while os.path.exists(out):
        out = os.path.join(folder, f"{base}_{n}{ext}")
        n += 1
    return out


def embed(src, out_dir, text, fmt, quality):
    """Watermark one file, save it, then read it back to verify."""
    with open(src, "rb") as f:
        data = f.read()
    with contextlib.redirect_stdout(io.StringIO()):  # silence debug prints from subsample.py
        jpg, png = apply_watermark(data, Filetype.PNG, jpeg_quality=quality, watermark=text)
    if fmt == "JXL":  # lossless only: lossy JXL can destroy the watermark
        buf = io.BytesIO()
        Image.open(io.BytesIO(png.getvalue())).save(buf, format="JXL", lossless=True)
        ext = ".jxl"
    else:
        buf, ext = (png, ".png") if fmt == "PNG" else (jpg, ".jpg")
    folder = out_dir or os.path.dirname(src)
    os.makedirs(folder, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0] + "_wm"
    out = unique_path(folder, base, ext)
    with open(out, "wb") as f:
        f.write(buf.getvalue())
    return out, bit_accuracy(out, text)


# ----------------------------------------------------------------- GUI
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ArtShield Watermarker (local)")
        self.geometry("760x640")
        self.files = []
        self.q = queue.Queue()
        self.text_var = tk.StringVar(value="SDV2")
        self.out_var = tk.StringVar()
        self.fmt_var = tk.StringVar(value="PNG")
        self.quality_var = tk.IntVar(value=95)
        self.dec_path = tk.StringVar()
        self.preview_img = None

        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self.enc_tab, self.dec_tab = ttk.Frame(tabs), ttk.Frame(tabs)
        tabs.add(self.enc_tab, text="Encode")
        tabs.add(self.dec_tab, text="Decode / check")
        self._build_encode()
        self._build_decode()
        self.after(100, self._poll)

    # --- encode tab
    def _build_encode(self):
        f = self.enc_tab
        top = ttk.Frame(f)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Add images...", command=self.add_files).pack(side="left")
        ttk.Button(top, text="Clear", command=self.clear_files).pack(side="left", padx=6)

        self.listbox = tk.Listbox(f, height=6)
        self.listbox.pack(fill="x", padx=6)

        opt = ttk.Frame(f)
        opt.pack(fill="x", padx=6, pady=8)
        ttk.Label(opt, text="Watermark text").grid(row=0, column=0, sticky="w")
        ttk.Entry(opt, textvariable=self.text_var, width=18).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(opt, text="Format").grid(row=0, column=2, sticky="e")
        ttk.Combobox(opt, textvariable=self.fmt_var, values=list(FORMATS),
                     width=12, state="readonly").grid(row=0, column=3, padx=6)
        ttk.Label(opt, text="JPEG quality").grid(row=0, column=4, sticky="e")
        ttk.Spinbox(opt, from_=50, to=100, textvariable=self.quality_var, width=5).grid(row=0, column=5, padx=6)
        ttk.Label(opt, text="Output folder").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(opt, textvariable=self.out_var, width=48).grid(row=1, column=1, columnspan=4, sticky="we", padx=6)
        ttk.Button(opt, text="Browse...", command=self.pick_out).grid(row=1, column=5)
        ttk.Label(f, text="Empty output folder = same folder as the source file. Result name: <name>_wm.<ext>",
                  foreground="gray").pack(anchor="w", padx=6)

        self.run_btn = ttk.Button(f, text="Run", command=self.run)
        self.run_btn.pack(pady=8)
        self.bar = ttk.Progressbar(f, mode="determinate")
        self.bar.pack(fill="x", padx=6)

        self.log = tk.Text(f, height=9, state="disabled")
        self.log.pack(fill="both", expand=True, padx=6, pady=6)
        self.preview = ttk.Label(f, text="(preview of last result)")
        self.preview.pack(pady=4)

    def add_files(self):
        for p in filedialog.askopenfilenames(filetypes=IMG_TYPES):
            if p not in self.files:
                self.files.append(p)
                self.listbox.insert("end", p)

    def clear_files(self):
        self.files.clear()
        self.listbox.delete(0, "end")

    def pick_out(self):
        d = filedialog.askdirectory()
        if d:
            self.out_var.set(d)

    def say(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self):
        try:
            text = validate_text(self.text_var.get())
        except ValueError as e:
            return messagebox.showerror("Invalid text", str(e))
        if not self.files:
            return messagebox.showinfo("Nothing to do", "Add some images first.")
        self.run_btn.state(["disabled"])
        self.bar.configure(maximum=len(self.files), value=0)
        args = (list(self.files), self.out_var.get().strip(), text,
                FORMATS[self.fmt_var.get()], int(self.quality_var.get()))
        threading.Thread(target=self._worker, args=args, daemon=True).start()

    def _worker(self, files, out_dir, text, fmt, quality):
        for i, src in enumerate(files, 1):
            name = os.path.basename(src)
            try:
                out, acc = embed(src, out_dir, text, fmt, quality)
                status = "OK" if acc == 1.0 else "VERIFY FAILED"
                self.q.put(("log", f"[{status}] {name} -> {os.path.basename(out)} (bit-acc {acc:.2f})"))
                self.q.put(("preview", out))
            except Exception as e:  # size outside 256..4096, corrupt file, etc.
                self.q.put(("log", f"[ERROR] {name}: {e}"))
            self.q.put(("progress", i))
        self.q.put(("done", None))

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.say(val)
                elif kind == "progress":
                    self.bar.configure(value=val)
                elif kind == "preview":
                    self.show_preview(val)
                elif kind == "done":
                    self.run_btn.state(["!disabled"])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def show_preview(self, path):
        if ImageTk is None:
            return
        try:
            im = Image.open(path).convert("RGB")
            im.thumbnail((240, 240))
            self.preview_img = ImageTk.PhotoImage(im)
            self.preview.configure(image=self.preview_img, text="")
        except Exception:
            pass

    # --- decode tab
    def _build_decode(self):
        f = self.dec_tab
        row = ttk.Frame(f)
        row.pack(fill="x", padx=6, pady=10)
        ttk.Entry(row, textvariable=self.dec_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=self.pick_dec).pack(side="left", padx=6)
        ttk.Label(f, text="Must match the watermark text on the Encode tab (default SDV2).").pack(anchor="w", padx=6)
        ttk.Button(f, text="Check watermark", command=self.check).pack(pady=10)
        self.dec_result = tk.Label(f, text="", justify="left", anchor="w", font=("TkDefaultFont", 11))
        self.dec_result.pack(fill="x", padx=10)
        ttk.Label(f, foreground="gray", wraplength=700, justify="left",
                  text="Note: an image with no watermark can still score 0.5-0.66 bit accuracy by chance. "
                       "Treat the watermark as readable only if accuracy is 1.00 (exact text match).").pack(anchor="w", padx=6, pady=10)

    def pick_dec(self):
        p = filedialog.askopenfilename(filetypes=IMG_TYPES)
        if p:
            self.dec_path.set(p)

    def check(self):
        try:
            text = validate_text(self.text_var.get())
            path = self.dec_path.get()
            bits = read_bits(path, len(text) * 8)
            expected = np.unpackbits(np.frombuffer(text.encode("ascii"), dtype=np.uint8))
            acc = float((bits == expected).mean())
            verdict = "READABLE" if acc == 1.0 else "not readable / damaged"
            self.dec_result.configure(
                text=f"Decoded text: {bits_to_text(bits)!r}\nBit accuracy: {acc:.2f}  ->  {verdict}")
        except Exception as e:
            self.dec_result.configure(text=f"Error: {e}")


if __name__ == "__main__":
    App().mainloop()
