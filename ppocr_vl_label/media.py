import os
import subprocess
import sys
import threading
import tkinter as tk
import urllib.request
from io import BytesIO
from tkinter import messagebox

try:
    from PIL import Image, ImageOps, ImageTk
except Exception:
    Image = ImageOps = ImageTk = None


def open_with_system(path: str):
    if not path:
        return
    if path.startswith(("http://", "https://")):
        import webbrowser

        webbrowser.open(path)
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as exc:
        messagebox.showerror("打开失败", f"无法打开媒体文件：\n{exc}")


class MediaCache:
    def __init__(self, path_resolver):
        self.path_resolver = path_resolver
        self.lock = threading.Lock()
        self.bytes_cache: dict[str, bytes] = {}
        self.image_cache: dict[tuple[str, tuple[int, int]], object] = {}
        self.photo_cache: dict[tuple[str, tuple[int, int], str], object] = {}

    def clear(self):
        with self.lock:
            self.bytes_cache.clear()
            self.image_cache.clear()
            self.photo_cache.clear()

    def _load_source_bytes(self, source: str) -> bytes:
        with self.lock:
            if source in self.bytes_cache:
                return self.bytes_cache[source]
        if source.startswith(("http://", "https://")):
            request = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read()
        else:
            path = self.path_resolver(source)
            if path is None or not path.exists():
                raise FileNotFoundError("无法解析图片路径。")
            data = path.read_bytes()
        with self.lock:
            self.bytes_cache[source] = data
        return data

    def get_pil_image(self, source: str, size: tuple[int, int]):
        if Image is None or ImageOps is None:
            raise RuntimeError("未安装 pillow，无法处理图片。")
        cache_key = (source, size)
        with self.lock:
            if cache_key in self.image_cache:
                return self.image_cache[cache_key].copy()
        img = Image.open(BytesIO(self._load_source_bytes(source))).convert("RGB")
        img = ImageOps.contain(img, size)
        with self.lock:
            self.image_cache[cache_key] = img.copy()
        return img

    def get_photo_image(self, source: str, size: tuple[int, int], theme_name: str, background: str):
        if ImageTk is None:
            raise RuntimeError("未安装 pillow，无法创建预览图。")
        cache_key = (source, size, theme_name)
        if cache_key in self.photo_cache:
            return self.photo_cache[cache_key]
        img = self.get_pil_image(source, size)
        canvas = Image.new("RGB", size, background)
        canvas.paste(img, ((size[0] - img.size[0]) // 2, (size[1] - img.size[1]) // 2))
        photo = ImageTk.PhotoImage(canvas)
        self.photo_cache[cache_key] = photo
        return photo

    def pil_to_photo(self, pil_image, size: tuple[int, int], background: str):
        if Image is None or ImageTk is None:
            raise RuntimeError("未安装 pillow，无法创建预览图。")
        canvas = Image.new("RGB", size, background)
        canvas.paste(pil_image, ((size[0] - pil_image.size[0]) // 2, (size[1] - pil_image.size[1]) // 2))
        return ImageTk.PhotoImage(canvas)


class AsyncMediaLoader:
    def __init__(self, root: tk.Tk, media_cache: MediaCache):
        self.root = root
        self.media_cache = media_cache

    def request_image(self, source: str, size: tuple[int, int], on_success, on_error):
        def worker():
            try:
                image = self.media_cache.get_pil_image(source, size)
            except Exception as exc:
                self.root.after(0, lambda: on_error(exc))
                return
            self.root.after(0, lambda: on_success(image))

        threading.Thread(target=worker, daemon=True).start()
