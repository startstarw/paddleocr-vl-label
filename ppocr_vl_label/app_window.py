import json
import tkinter as tk
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .media import AsyncMediaLoader, MediaCache, open_with_system
from .models import LABEL_TO_MEDIA, MEDIA_LABELS, TAG_VALUES, MediaItem, Sample, TextItem
from .controllers.preview_controller import PREVIEW_MODES, PreviewController
from .themes import THEMES


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SFT VL 数据集标注工具")
        self.root.geometry("1640x960")
        self.root.minsize(1380, 840)
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.samples, self.current_index, self.current_file = [], None, None
        self.preview_image, self.drag_media_index = None, None
        self.pending_preview_job: Optional[str] = None
        self.preview_request_id = 0
        self.preview_mode_var = tk.StringVar(value=PREVIEW_MODES[0])
        self.theme_var = tk.StringVar(value="浅色")
        self.status_var = tk.StringVar(value="就绪")
        self.preview_path_var = tk.StringVar(value="当前未选择媒体")
        self.media_type_var = tk.StringVar(value="图片")
        self.is_system_var = tk.IntVar(value=0)
        self.text_tag_var = tk.StringVar(value="mask")
        self.media_url_var = tk.StringVar()
        self.media_match_var = tk.StringVar(value="0")
        self.media_cache = MediaCache(self.resolve_media_path)
        self.media_loader = AsyncMediaLoader(self.root, self.media_cache)
        self.preview_controller = PreviewController(self)
        self._build()
        self.apply_theme()
        self.new_sample()

    def _build(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        header = ttk.Frame(self.root, padding=(16, 14, 16, 8), style="Toolbar.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=1)
        title_box = ttk.Frame(header, style="Toolbar.TFrame")
        title_box.grid(row=0, column=0, sticky="w")
        ttk.Label(title_box, text="SFT VL 数据集标注工具", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="支持缩略图浏览、拖拽排序、主题切换与 JSONL 导出", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))
        toolbar = ttk.Frame(header, style="Toolbar.TFrame")
        toolbar.grid(row=0, column=1, sticky="e")
        for text, cmd in [("新建项目", self.new_project), ("打开 JSONL", self.load_jsonl), ("保存 JSONL", self.save_jsonl), ("新增样本", self.new_sample), ("删除样本", self.delete_sample), ("校验样本", self.validate_current_sample)]:
            ttk.Button(toolbar, text=text, command=cmd, style="Primary.TButton").pack(side="left", padx=(8, 0))
        ttk.Label(toolbar, text="主题", style="Subtitle.TLabel").pack(side="left", padx=(16, 6))
        theme_box = ttk.Combobox(toolbar, textvariable=self.theme_var, values=list(THEMES), width=6, state="readonly")
        theme_box.pack(side="left")
        theme_box.bind("<<ComboboxSelected>>", lambda e: self.apply_theme())
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        body = ttk.Frame(self.root, padding=(16, 8, 16, 16), style="App.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        left = ttk.LabelFrame(body, text="样本列表", padding=10, style="Card.TLabelframe")
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text="当前工程中的全部样本", style="PanelSub.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.sample_listbox = tk.Listbox(left, width=30, exportselection=False, bd=0, highlightthickness=0, font=("Consolas", 10))
        self.sample_listbox.grid(row=1, column=0, sticky="ns")
        self.sample_listbox.bind("<<ListboxSelect>>", self.on_sample_selected)

        main = ttk.Frame(body, style="App.TFrame")
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=4)
        main.columnconfigure(1, weight=9)
        main.rowconfigure(1, weight=1)
        meta = ttk.LabelFrame(main, text="样本设置", padding=10, style="Card.TLabelframe")
        meta.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Label(meta, text="媒体类型", style="PanelBody.TLabel").grid(row=0, column=0, sticky="w")
        media_box = ttk.Combobox(meta, textvariable=self.media_type_var, values=list(LABEL_TO_MEDIA), state="readonly", width=8)
        media_box.grid(row=0, column=1, padx=(6, 16), sticky="w")
        media_box.bind("<<ComboboxSelected>>", lambda e: self.on_meta_changed())
        ttk.Checkbutton(meta, text="系统提示词模式", variable=self.is_system_var, command=self.on_meta_changed).grid(row=0, column=2, sticky="w")
        ttk.Button(meta, text="预览当前媒体", command=self.preview_controller.preview_selected_media, style="Primary.TButton").grid(row=0, column=3, padx=(16, 0))
        ttk.Button(meta, text="外部打开媒体", command=self.open_selected_media, style="Primary.TButton").grid(row=0, column=4, padx=(6, 0))

        editor = ttk.Frame(main, style="App.TFrame")
        editor.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        editor.rowconfigure(1, weight=1)
        editor.rowconfigure(3, weight=1)
        editor.columnconfigure(0, weight=1)
        text_frame = ttk.LabelFrame(editor, text="文本内容 text_info", padding=10, style="Card.TLabelframe")
        text_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", pady=(0, 8))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.text_tree = ttk.Treeview(text_frame, columns=("index", "tag", "text"), show="headings", height=12)
        for col, title, width in [("index", "#", 42), ("tag", "标签", 84), ("text", "文本", 690)]:
            self.text_tree.heading(col, text=title)
            self.text_tree.column(col, width=width, anchor="center" if col != "text" else "w")
        self.text_tree.grid(row=0, column=0, sticky="nsew")
        self.text_tree.bind("<<TreeviewSelect>>", self.on_text_selected)
        btns = ttk.Frame(text_frame, style="Inner.TFrame")
        btns.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for text, cmd in [("新增文本", self.add_text_item), ("删除文本", self.delete_text_item), ("上移", lambda: self.move_text_item(-1)), ("下移", lambda: self.move_text_item(1))]:
            ttk.Button(btns, text=text, command=cmd).pack(side="left", padx=(6, 0))
        edit_bar = ttk.Frame(editor, style="App.TFrame")
        edit_bar.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(edit_bar, text="标签", style="PanelBody.TLabel").grid(row=0, column=0, sticky="w")
        tag_box = ttk.Combobox(edit_bar, textvariable=self.text_tag_var, values=TAG_VALUES, state="readonly", width=10)
        tag_box.grid(row=0, column=1, padx=(6, 16), sticky="w")
        tag_box.bind("<<ComboboxSelected>>", lambda e: self.update_selected_text())
        ttk.Button(edit_bar, text="应用文本修改", command=self.update_selected_text, style="Primary.TButton").grid(row=0, column=2, sticky="w")
        self.text_editor = tk.Text(editor, wrap="word", height=10, bd=0, highlightthickness=1, padx=10, pady=10, font=("Consolas", 10))
        self.text_editor.grid(row=3, column=0, sticky="nsew")

        right = ttk.Frame(main, style="App.TFrame")
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)
        media_frame = ttk.LabelFrame(right, text="媒体列表 image_info / video_info", padding=10, style="Card.TLabelframe")
        media_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        media_frame.columnconfigure(0, weight=1)
        media_frame.rowconfigure(0, weight=1)
        self.media_tree = ttk.Treeview(media_frame, columns=("index", "matched", "url"), show="headings", height=6)
        for col, title, width in [("index", "#", 42), ("matched", "关联文本索引", 120), ("url", "媒体路径 / URL", 380)]:
            self.media_tree.heading(col, text=title)
            self.media_tree.column(col, width=width, anchor="center" if col != "url" else "w")
        self.media_tree.grid(row=0, column=0, sticky="nsew")
        self.media_tree.bind("<<TreeviewSelect>>", self.on_media_selected)
        self.media_tree.bind("<ButtonPress-1>", self.on_media_drag_start)
        self.media_tree.bind("<B1-Motion>", self.on_media_drag_motion)
        self.media_tree.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag_media_index", None))
        media_btns = ttk.Frame(media_frame, style="Inner.TFrame")
        media_btns.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for text, cmd in [("新增媒体", self.add_media_item), ("删除媒体", self.delete_media_item), ("浏览文件", self.browse_media_path), ("上移", lambda: self.move_media_item(-1)), ("下移", lambda: self.move_media_item(1))]:
            ttk.Button(media_btns, text=text, command=cmd).pack(side="left", padx=(6, 0))
        ttk.Label(media_btns, text="支持拖拽排序", style="PanelHint.TLabel").pack(side="right")

        media_edit = ttk.LabelFrame(right, text="媒体编辑", padding=10, style="Card.TLabelframe")
        media_edit.grid(row=1, column=0, sticky="ew")
        media_edit.columnconfigure(1, weight=1)
        ttk.Label(media_edit, text="路径 / URL", style="PanelBody.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(media_edit, textvariable=self.media_url_var).grid(row=0, column=1, sticky="ew", padx=(6, 6))
        ttk.Label(media_edit, text="关联到文本", style="PanelBody.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(media_edit, from_=0, to=9999, textvariable=self.media_match_var, width=8).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(6, 0))
        ttk.Button(media_edit, text="应用媒体修改", command=self.update_selected_media, style="Primary.TButton").grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        preview = ttk.LabelFrame(right, text="预览区", padding=10, style="Card.TLabelframe")
        preview.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(1, weight=1)
        preview_top = ttk.Frame(preview, style="Inner.TFrame")
        preview_top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        preview_top.columnconfigure(1, weight=1)
        ttk.Label(preview_top, text="预览模式", style="PanelBody.TLabel").grid(row=0, column=0, sticky="w")
        preview_mode_box = ttk.Combobox(preview_top, textvariable=self.preview_mode_var, values=PREVIEW_MODES, width=10, state="readonly")
        preview_mode_box.grid(row=0, column=1, sticky="w", padx=(8, 0))
        preview_mode_box.bind("<<ComboboxSelected>>", self.preview_controller.on_preview_mode_changed)
        preview_view = ttk.Frame(preview, style="Inner.TFrame")
        preview_view.grid(row=1, column=0, sticky="nsew")
        preview_view.columnconfigure(0, weight=1)
        preview_view.rowconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(preview_view, bd=0, highlightthickness=0)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", self.preview_controller.on_preview_canvas_resized)
        preview_y = ttk.Scrollbar(preview_view, orient="vertical", command=self.preview_canvas.yview)
        preview_y.grid(row=0, column=1, sticky="ns")
        preview_x = ttk.Scrollbar(preview_view, orient="horizontal", command=self.preview_canvas.xview)
        preview_x.grid(row=1, column=0, sticky="ew")
        self.preview_canvas.configure(xscrollcommand=preview_x.set, yscrollcommand=preview_y.set)
        ttk.Label(preview, textvariable=self.preview_path_var, style="PanelSub.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 0))

    def theme(self):
        return THEMES[self.theme_var.get()]

    def apply_theme(self):
        t = self.theme()
        self.root.configure(bg=t["root"])
        self.style.configure("App.TFrame", background=t["root"])
        self.style.configure("Toolbar.TFrame", background=t["root"])
        self.style.configure("Inner.TFrame", background=t["panel"])
        self.style.configure("Title.TLabel", background=t["root"], foreground=t["text"], font=("Segoe UI Semibold", 18))
        self.style.configure("Subtitle.TLabel", background=t["root"], foreground=t["sub"], font=("Segoe UI", 10))
        self.style.configure("Status.TLabel", background=t["soft"], foreground=t["accent"], padding=(12, 6), font=("Segoe UI Semibold", 9))
        self.style.configure("PanelBody.TLabel", background=t["panel"], foreground=t["text"], font=("Segoe UI", 10))
        self.style.configure("PanelSub.TLabel", background=t["panel"], foreground=t["sub"], font=("Segoe UI", 10))
        self.style.configure("PanelHint.TLabel", background=t["panel"], foreground=t["sub"], font=("Segoe UI", 9))
        self.style.configure("Card.TLabelframe", background=t["panel"], borderwidth=1, relief="solid")
        self.style.configure("Card.TLabelframe.Label", background=t["panel"], foreground=t["text"], font=("Segoe UI Semibold", 10))
        self.style.configure("Primary.TButton", padding=(12, 8), font=("Segoe UI Semibold", 9))
        self.style.map("Primary.TButton", background=[("active", t["active"]), ("!disabled", t["soft"])], foreground=[("!disabled", t["accent"])])
        self.style.configure("Treeview", rowheight=28, fieldbackground=t["panel"], background=t["panel"], foreground=t["text"])
        self.style.configure("Treeview.Heading", background=t["alt"], foreground=t["sub"], font=("Segoe UI Semibold", 9))
        self.style.map("Treeview", background=[("selected", t["selbg"])], foreground=[("selected", t["selfg"])])
        self.sample_listbox.configure(bg=t["panel"], fg=t["text"], selectbackground=t["selbg"], selectforeground=t["selfg"])
        self.text_editor.configure(bg=t["input"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent"])
        self.preview_canvas.configure(bg=t["alt"])
        if self.current_sample():
            self.preview_controller.preview_selected_media()

    def refresh_sample_list(self):
        self.sample_listbox.delete(0, tk.END)
        for i, s in enumerate(self.samples, 1):
            mode = "系统" if s.is_system else MEDIA_LABELS[s.media_type]
            self.sample_listbox.insert(tk.END, f"{i:03d} [{mode}] 文本{len(s.text_info)} 媒体{len(s.media_info)}")

    def current_sample(self):
        if self.current_index is None or not (0 <= self.current_index < len(self.samples)):
            return None
        return self.samples[self.current_index]

    def select_sample(self, idx: int):
        if not self.samples:
            return
        self.current_index = idx
        self.sample_listbox.selection_clear(0, tk.END)
        self.sample_listbox.selection_set(idx)
        self.sample_listbox.activate(idx)
        self.load_sample()

    def on_sample_selected(self, event=None):
        sel = self.sample_listbox.curselection()
        if sel:
            self.current_index = sel[0]
            self.media_cache.clear()
            self.load_sample()

    def load_sample(self):
        s = self.current_sample()
        if not s:
            return
        self.media_type_var.set(MEDIA_LABELS[s.media_type])
        self.is_system_var.set(s.is_system)
        self.refresh_text_tree()
        self.refresh_media_tree()
        self.preview_controller.clear_preview("请选择要预览的媒体。\n视频暂不支持内嵌播放，请使用外部程序打开。")

    def new_project(self):
        if self.samples and not messagebox.askyesno("确认操作", "是否丢弃当前尚未保存的数据？"):
            return
        self.samples = []
        self.current_file = None
        self.media_cache.clear()
        self.new_sample()
        self.status_var.set("已新建项目")

    def new_sample(self):
        self.samples.append(Sample("image", 0, [TextItem("", "mask"), TextItem("", "no_mask")], [MediaItem("", 0)]))
        self.refresh_sample_list()
        self.select_sample(len(self.samples) - 1)
        self.status_var.set("已新增样本")

    def delete_sample(self):
        if self.current_index is None or not self.samples:
            return
        if not messagebox.askyesno("删除样本", "是否删除当前选中的样本？"):
            return
        del self.samples[self.current_index]
        if not self.samples:
            self.current_index = None
            self.new_sample()
            return
        self.refresh_sample_list()
        self.select_sample(min(self.current_index, len(self.samples) - 1))
        self.status_var.set("已删除样本")

    def on_meta_changed(self):
        s = self.current_sample()
        if not s:
            return
        s.media_type = LABEL_TO_MEDIA[self.media_type_var.get()]
        s.is_system = int(self.is_system_var.get())
        self.refresh_sample_list()
        if self.current_index is not None:
            self.sample_listbox.selection_set(self.current_index)

    def refresh_text_tree(self):
        s = self.current_sample()
        self.text_tree.delete(*self.text_tree.get_children())
        if not s:
            return
        for i, item in enumerate(s.text_info):
            self.text_tree.insert("", "end", iid=str(i), values=(i, item.tag, item.text.replace("\n", " ")[:120]))
        if s.text_info:
            self.text_tree.selection_set("0")
            self.on_text_selected()

    def refresh_media_tree(self):
        s = self.current_sample()
        self.media_tree.delete(*self.media_tree.get_children())
        if not s:
            return
        for i, item in enumerate(s.media_info):
            self.media_tree.insert("", "end", iid=str(i), values=(i, item.matched_text_index, item.media_url))
        if s.media_info:
            self.select_media_index(0)

    def resolve_media_source(self, media_path: str) -> Optional[str]:
        if not media_path:
            return None
        if media_path.startswith(("http://", "https://")):
            return media_path
        path = self.resolve_media_path(media_path)
        if path is None or not path.exists():
            return None
        return media_path

    def on_text_selected(self, event=None):
        s, sel = self.current_sample(), self.text_tree.selection()
        if not s or not sel:
            return
        item = s.text_info[int(sel[0])]
        self.text_tag_var.set(item.tag)
        self.text_editor.delete("1.0", tk.END)
        self.text_editor.insert("1.0", item.text)

    def on_media_selected(self, event=None):
        s, sel = self.current_sample(), self.media_tree.selection()
        if not s or not sel:
            return
        item = s.media_info[int(sel[0])]
        self.media_url_var.set(item.media_url)
        self.media_match_var.set(str(item.matched_text_index))
        self.preview_controller.schedule_preview()

    def add_text_item(self):
        s = self.current_sample()
        if not s:
            return
        next_tag = "no_mask" if s.text_info and s.text_info[-1].tag == "mask" else "mask"
        s.text_info.append(TextItem("", next_tag))
        self.refresh_text_tree()
        self.status_var.set("已新增文本")

    def delete_text_item(self):
        s, sel = self.current_sample(), self.text_tree.selection()
        if not s or not sel:
            return
        del s.text_info[int(sel[0])]
        if not s.text_info:
            s.text_info = [TextItem("", "mask"), TextItem("", "no_mask")]
        for m in s.media_info:
            m.matched_text_index = min(max(m.matched_text_index, 0), len(s.text_info) - 1)
        self.refresh_text_tree()
        self.refresh_media_tree()

    def move_text_item(self, step: int):
        s, sel = self.current_sample(), self.text_tree.selection()
        if not s or not sel:
            return
        i, j = int(sel[0]), int(sel[0]) + step
        if j < 0 or j >= len(s.text_info):
            return
        s.text_info[i], s.text_info[j] = s.text_info[j], s.text_info[i]
        for m in s.media_info:
            if m.matched_text_index == i:
                m.matched_text_index = j
            elif m.matched_text_index == j:
                m.matched_text_index = i
        self.refresh_text_tree()
        self.refresh_media_tree()
        self.text_tree.selection_set(str(j))
        self.on_text_selected()

    def update_selected_text(self):
        s, sel = self.current_sample(), self.text_tree.selection()
        if not s or not sel:
            return
        i = int(sel[0])
        s.text_info[i].tag = self.text_tag_var.get()
        s.text_info[i].text = self.text_editor.get("1.0", tk.END).rstrip()
        self.refresh_text_tree()
        self.text_tree.selection_set(str(i))
        self.status_var.set("已更新文本")

    def add_media_item(self):
        s = self.current_sample()
        if not s:
            return
        s.media_info.append(MediaItem("", 0))
        self.refresh_media_tree()
        self.select_media_index(len(s.media_info) - 1)
        self.status_var.set("已新增媒体")

    def delete_media_item(self):
        s, sel = self.current_sample(), self.media_tree.selection()
        if not s or not sel:
            return
        del s.media_info[int(sel[0])]
        self.refresh_media_tree()
        self.status_var.set("已删除媒体")

    def move_media_item(self, step: int):
        s, sel = self.current_sample(), self.media_tree.selection()
        if not s or not sel:
            return
        i, j = int(sel[0]), int(sel[0]) + step
        if j < 0 or j >= len(s.media_info):
            return
        s.media_info[i], s.media_info[j] = s.media_info[j], s.media_info[i]
        self.refresh_media_tree()
        self.select_media_index(j)
        self.status_var.set("已调整媒体顺序")

    def select_media_index(self, idx: int):
        s = self.current_sample()
        if not s or idx < 0 or idx >= len(s.media_info):
            return
        self.media_tree.selection_set(str(idx))
        self.media_tree.focus(str(idx))
        self.media_tree.see(str(idx))
        self.on_media_selected()

    def on_media_drag_start(self, event):
        row = self.media_tree.identify_row(event.y)
        self.drag_media_index = int(row) if row else None

    def on_media_drag_motion(self, event):
        if self.drag_media_index is None:
            return
        row = self.media_tree.identify_row(event.y)
        if not row:
            return
        target = int(row)
        if target == self.drag_media_index:
            return
        s = self.current_sample()
        if not s:
            return
        item = s.media_info.pop(self.drag_media_index)
        s.media_info.insert(target, item)
        self.drag_media_index = target
        self.refresh_media_tree()
        self.select_media_index(target)
        self.status_var.set("已拖拽调整媒体顺序")

    def update_selected_media(self):
        s, sel = self.current_sample(), self.media_tree.selection()
        if not s or not sel:
            return
        try:
            matched = int(self.media_match_var.get())
        except ValueError:
            messagebox.showerror("数值错误", "`matched_text_index` 必须是整数。")
            return
        i = int(sel[0])
        s.media_info[i].media_url = self.media_url_var.get().strip()
        s.media_info[i].matched_text_index = matched
        self.refresh_media_tree()
        self.select_media_index(i)
        self.status_var.set("已更新媒体")

    def browse_media_path(self):
        path = filedialog.askopenfilename(title="选择媒体文件", filetypes=[("支持的媒体", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.mp4 *.avi *.mov *.mkv"), ("所有文件", "*.*")])
        if path:
            self.media_url_var.set(path)
            self.update_selected_media()

    def resolve_media_path(self, media_path: str):
        if not media_path or media_path.startswith(("http://", "https://")):
            return None
        p = Path(media_path)
        if p.is_absolute() and p.exists():
            return p
        roots = ([self.current_file.parent] if self.current_file else []) + [Path.cwd()]
        rel = Path(*PurePosixPath(media_path).parts)
        for root in roots:
            rp = (root / rel).resolve()
            if rp.exists():
                return rp
        return p

    def open_selected_media(self):
        s, sel = self.current_sample(), self.media_tree.selection()
        if not s or not sel:
            return
        raw = s.media_info[int(sel[0])].media_url.strip()
        path = self.resolve_media_path(raw)
        open_with_system(str(path) if path is not None else raw)

    def validate_sample(self, s: Sample):
        errors = []
        if not s.text_info:
            errors.append("`text_info` 不能为空。")
        if not s.media_info:
            errors.append("`image_info` / `video_info` 不能为空。")
        if s.is_system and len(s.text_info) < 2:
            errors.append("系统提示词模式下，至少需要包含一组系统文本及回复。")
        for i, item in enumerate(s.text_info):
            if item.tag not in TAG_VALUES:
                errors.append(f"`text_info[{i}].tag` 只能是 `mask` 或 `no_mask`。")
            if not item.text.strip():
                errors.append(f"`text_info[{i}].text` 不能为空。")
        for i in range(1, len(s.text_info)):
            if s.text_info[i].tag == s.text_info[i - 1].tag:
                errors.append("`text_info` 中的标签需要在 `mask` 和 `no_mask` 之间交替出现。")
                break
        for i, item in enumerate(s.media_info):
            if not item.media_url.strip():
                errors.append(f"第 {i} 个媒体项的 `image_url` 不能为空。")
            if item.matched_text_index < 0 or item.matched_text_index >= len(s.text_info):
                errors.append(f"第 {i} 个媒体项的 `matched_text_index` 超出范围。")
        return errors

    def validate_current_sample(self):
        s = self.current_sample()
        if not s:
            return False
        errors = self.validate_sample(s)
        if errors:
            messagebox.showwarning("校验结果", "\n".join(errors))
            self.status_var.set("校验发现问题")
            return False
        messagebox.showinfo("校验结果", "当前样本校验通过。")
        self.status_var.set("校验通过")
        return True

    def load_jsonl(self):
        path = filedialog.askopenfilename(title="打开 JSONL 文件", filetypes=[("JSONL 文件", "*.jsonl"), ("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.samples = [Sample.from_dict(json.loads(line)) for line in f if line.strip()]
        except Exception as exc:
            messagebox.showerror("加载失败", f"无法加载文件：\n{exc}")
            return
        if not self.samples:
            messagebox.showwarning("空文件", "文件中没有找到有效样本。")
            return
        self.current_file = Path(path)
        self.media_cache.clear()
        self.refresh_sample_list()
        self.current_index = 0
        self.sample_listbox.selection_clear(0, tk.END)
        self.sample_listbox.selection_set(0)
        self.sample_listbox.activate(0)
        self.status_var.set(f"已加载 {len(self.samples)} 条样本，正在准备首个样本…")
        self.root.after_idle(lambda: self.select_sample(0))

    def save_jsonl(self):
        bad = [i + 1 for i, s in enumerate(self.samples) if self.validate_sample(s)]
        if bad and not messagebox.askyesno("校验警告", f"样本 {bad} 存在校验问题。\n是否仍然继续保存？"):
            return
        path = filedialog.asksaveasfilename(title="保存 JSONL 文件", defaultextension=".jsonl", filetypes=[("JSONL 文件", "*.jsonl"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for s in self.samples:
                    f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
        except Exception as exc:
            messagebox.showerror("保存失败", f"无法保存文件：\n{exc}")
            return
        self.current_file = Path(path)
        self.status_var.set(f"已保存到 {path}")
        messagebox.showinfo("保存成功", f"已保存 {len(self.samples)} 条样本。")

