import tkinter as tk
from pathlib import Path

from .media import Image, ImageOps, ImageTk


PREVIEW_MODES = ("适应窗口", "原始比例", "1:1")


class PreviewController:
    def __init__(self, app):
        self.app = app

    def schedule_preview(self, delay_ms: int = 80):
        if self.app.pending_preview_job is not None:
            self.app.root.after_cancel(self.app.pending_preview_job)
        self.app.pending_preview_job = self.app.root.after(delay_ms, self.preview_selected_media)

    def on_preview_mode_changed(self, _event=None):
        self.schedule_preview(10)

    def on_preview_canvas_resized(self, _event=None):
        if self.app.preview_mode_var.get() != "1:1":
            self.schedule_preview(120)

    def get_preview_canvas_size(self):
        self.app.root.update_idletasks()
        width = max(self.app.preview_canvas.winfo_width(), 320)
        height = max(self.app.preview_canvas.winfo_height(), 240)
        return max(width - 4, 1), max(height - 4, 1)

    def show_preview_message(self, msg: str):
        self.app.preview_canvas.delete("all")
        self.app.preview_canvas.create_text(
            max(self.app.preview_canvas.winfo_width() // 2, 160),
            max(self.app.preview_canvas.winfo_height() // 2, 120),
            text=msg,
            width=max(self.app.preview_canvas.winfo_width() - 40, 240),
            fill=self.app.theme()["sub"],
            justify="center",
            font=("Segoe UI", 11),
        )
        self.app.preview_canvas.configure(
            scrollregion=(
                0,
                0,
                self.app.preview_canvas.winfo_width(),
                self.app.preview_canvas.winfo_height(),
            )
        )

    def show_preview_photo(self, photo, image_size: tuple[int, int]):
        canvas_width = max(self.app.preview_canvas.winfo_width(), image_size[0])
        canvas_height = max(self.app.preview_canvas.winfo_height(), image_size[1])
        x = max((canvas_width - image_size[0]) // 2, 0)
        y = max((canvas_height - image_size[1]) // 2, 0)
        self.app.preview_canvas.delete("all")
        self.app.preview_canvas.create_image(x, y, anchor="nw", image=photo)
        self.app.preview_canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))

    def update_preview_from_pil(self, pil_image):
        mode = self.app.preview_mode_var.get()
        render_image = pil_image.copy()
        if ImageOps is not None:
            viewport = self.get_preview_canvas_size()
            if mode == "适应窗口":
                render_image = ImageOps.contain(render_image, viewport)
            elif mode == "原始比例" and (render_image.width > viewport[0] or render_image.height > viewport[1]):
                render_image = ImageOps.contain(render_image, viewport)
        self.app.preview_image = ImageTk.PhotoImage(render_image)
        self.show_preview_photo(self.app.preview_image, render_image.size)

    def clear_preview(self, msg: str):
        if self.app.pending_preview_job is not None:
            self.app.root.after_cancel(self.app.pending_preview_job)
            self.app.pending_preview_job = None
        self.app.preview_request_id += 1
        self.app.preview_image = None
        self.show_preview_message(msg)
        self.app.preview_path_var.set("当前未选择媒体")

    def preview_selected_media(self):
        self.app.pending_preview_job = None
        self.app.preview_request_id += 1
        request_id = self.app.preview_request_id
        sample = self.app.current_sample()
        selection = self.app.media_tree.selection()
        if not sample or not selection:
            return
        item = sample.media_info[int(selection[0])]
        media_path = item.media_url.strip()
        if not media_path:
            self.clear_preview("当前媒体路径为空。")
            return
        self.app.preview_path_var.set(media_path)
        if sample.media_type == "video":
            self.show_preview_message(f"当前是视频文件：\n{media_path}\n\n请使用“外部打开媒体”进行查看。")
            self.app.preview_image = None
            return
        source = self.app.resolve_media_source(media_path)
        if source is None:
            self.clear_preview("无法解析当前图片路径。")
            return
        self.show_preview_message("正在加载预览…")
        try:
            if Image and ImageTk and ImageOps:
                def on_success(pil_image):
                    if request_id != self.app.preview_request_id:
                        return
                    self.update_preview_from_pil(pil_image)
                    if media_path.startswith(("http://", "https://")):
                        self.app.preview_path_var.set(media_path)
                    else:
                        self.app.preview_path_var.set(str(self.app.resolve_media_path(media_path)))

                def on_error(exc):
                    if request_id != self.app.preview_request_id:
                        return
                    self.show_preview_message(f"预览失败：\n{exc}")
                    self.app.preview_image = None

                self.app.media_loader.request_original_image(source, on_success, on_error)
                return

            if media_path.startswith(("http://", "https://")):
                raise RuntimeError("远程图片预览需要先安装 `pillow`。")
            path = self.app.resolve_media_path(media_path)
            if Path(media_path).suffix.lower() not in {".png", ".gif"}:
                raise RuntimeError("如需预览 jpg/webp/bmp 等图片，请先安装 `pillow`。")
            if path is None or not path.exists():
                raise FileNotFoundError("无法解析图片路径。")
            self.app.preview_image = tk.PhotoImage(file=str(path))
            self.show_preview_photo(
                self.app.preview_image,
                (self.app.preview_image.width(), self.app.preview_image.height()),
            )
            self.app.preview_path_var.set(str(path))
        except Exception as exc:
            self.show_preview_message(f"预览失败：\n{exc}")
            self.app.preview_image = None
