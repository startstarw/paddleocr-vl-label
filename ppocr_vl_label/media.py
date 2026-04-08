import os
import subprocess
import sys
import threading
import tkinter as tk
import urllib.request
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
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
    def __init__(
        self,
        path_resolver,
        max_bytes_entries: int = 24,
        max_original_entries: int = 24,
        max_resized_entries: int = 48,
        max_photo_entries: int = 48,
    ):
        self.path_resolver = path_resolver
        self.lock = threading.Lock()
        self.max_bytes_entries = max_bytes_entries
        self.max_original_entries = max_original_entries
        self.max_resized_entries = max_resized_entries
        self.max_photo_entries = max_photo_entries
        self.bytes_cache: OrderedDict[str, bytes] = OrderedDict()
        self.original_image_cache: OrderedDict[str, object] = OrderedDict()
        self.resized_image_cache: OrderedDict[tuple[str, tuple[int, int]], object] = OrderedDict()
        self.photo_cache: OrderedDict[tuple[str, tuple[int, int], str], object] = OrderedDict()

    def clear(self):
        with self.lock:
            self.bytes_cache.clear()
            self.original_image_cache.clear()
            self.resized_image_cache.clear()
            self.photo_cache.clear()

    def _normalize_source(self, source: str) -> str:
        if source.startswith(("http://", "https://")):
            return source
        path = self.path_resolver(source)
        if path is None:
            return source
        try:
            return str(Path(path).resolve())
        except Exception:
            return str(path)

    def _remember(self, cache: OrderedDict, key, value, limit: int):
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)

    def get_cache_stats(self):
        with self.lock:
            return {
                "bytes": len(self.bytes_cache),
                "original": len(self.original_image_cache),
                "resized": len(self.resized_image_cache),
                "photo": len(self.photo_cache),
            }

    def get_original_pil_image(self, source: str):
        if Image is None:
            raise RuntimeError("未安装 pillow，无法处理图片。")
        cache_key = self._normalize_source(source)
        with self.lock:
            if cache_key in self.original_image_cache:
                image = self.original_image_cache[cache_key]
                self.original_image_cache.move_to_end(cache_key)
                return image.copy()
        img = Image.open(BytesIO(self._load_source_bytes(source))).convert("RGB")
        with self.lock:
            self._remember(self.original_image_cache, cache_key, img.copy(), self.max_original_entries)
        return img

    def _load_source_bytes(self, source: str) -> bytes:
        cache_key = self._normalize_source(source)
        with self.lock:
            if cache_key in self.bytes_cache:
                data = self.bytes_cache[cache_key]
                self.bytes_cache.move_to_end(cache_key)
                return data
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
            self._remember(self.bytes_cache, cache_key, data, self.max_bytes_entries)
        return data

    def get_pil_image(self, source: str, size: tuple[int, int]):
        if Image is None or ImageOps is None:
            raise RuntimeError("未安装 pillow，无法处理图片。")
        cache_key = (self._normalize_source(source), size)
        with self.lock:
            if cache_key in self.resized_image_cache:
                image = self.resized_image_cache[cache_key]
                self.resized_image_cache.move_to_end(cache_key)
                return image.copy()
        img = ImageOps.contain(self.get_original_pil_image(source), size)
        with self.lock:
            self._remember(self.resized_image_cache, cache_key, img.copy(), self.max_resized_entries)
        return img

    def get_photo_image(self, source: str, size: tuple[int, int], theme_name: str, background: str):
        if ImageTk is None:
            raise RuntimeError("未安装 pillow，无法创建预览图。")
        cache_key = (self._normalize_source(source), size, theme_name)
        with self.lock:
            if cache_key in self.photo_cache:
                photo = self.photo_cache[cache_key]
                self.photo_cache.move_to_end(cache_key)
                return photo
        img = self.get_pil_image(source, size)
        canvas = Image.new("RGB", size, background)
        canvas.paste(img, ((size[0] - img.size[0]) // 2, (size[1] - img.size[1]) // 2))
        photo = ImageTk.PhotoImage(canvas)
        with self.lock:
            self._remember(self.photo_cache, cache_key, photo, self.max_photo_entries)
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

    def request_original_image(self, source: str, on_success, on_error):
        def worker():
            try:
                image = self.media_cache.get_original_pil_image(source)
            except Exception as exc:
                self.root.after(0, lambda: on_error(exc))
                return
            self.root.after(0, lambda: on_success(image))

        threading.Thread(target=worker, daemon=True).start()
