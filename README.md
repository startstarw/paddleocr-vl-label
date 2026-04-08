# SFT VL 数据集标注工具

这是一个本地桌面 GUI 工具，用来标注并导出符合 SFT VL 数据集格式的 `jsonl` 文件。

## 项目结构

当前代码已经做了基础模块化拆分：

- `app.py`：程序启动入口
- `ppocr_vl_label/app_window.py`：主窗口编排与样本编辑逻辑
- `ppocr_vl_label/models.py`：数据模型
- `ppocr_vl_label/media.py`：媒体缓存、异步加载、外部打开
- `ppocr_vl_label/preview_controller.py`：预览模式、预览渲染与预览加载控制
- `ppocr_vl_label/themes.py`：主题配置

当前版本支持：

- 创建和管理多个样本
- 编辑 `text_info`
- 编辑 `image_info` 或 `video_info`
- 预览图片并显示缩略图栏
- 多图点击切换与媒体顺序调整
- 支持拖拽重排媒体顺序
- 支持浅色 / 暗色主题切换
- 设置 `mask` / `no_mask`
- 设置 `matched_text_index`
- 设置 `is_system`
- 导入已有 `jsonl`
- 导出为按行分隔的 JSON 样本
- 对样本做基础格式校验

## 快速开始

```bash
python app.py
```

如果你希望在 GUI 中直接预览本地图片，建议安装 `pillow`：

```bash
pip install pillow
```

即使没有安装 `pillow`，工具也可以正常使用，只是部分图片格式无法内嵌预览，仍然可以通过系统默认程序打开媒体文件。

## 数据格式

导出的每一行都是一个 JSON 样本，例如：

```json
{
  "image_info": [
    {
      "matched_text_index": 0,
      "image_url": "./demo/0.png"
    }
  ],
  "text_info": [
    {
      "text": "图片里是什么？",
      "tag": "mask"
    },
    {
      "text": "这是一页文档图片。",
      "tag": "no_mask"
    }
  ]
}
```

视频样本会自动使用 `video_info` 字段。

## 推荐使用流程

1. 点击“新增样本”创建一个样本
2. 在 `text_info` 中录入问答内容
3. 在右侧添加图片或视频路径
4. 通过缩略图栏快速切换不同媒体
5. 用“上移 / 下移”或直接拖拽调整多图顺序
6. 设置每个媒体对应的 `matched_text_index`
7. 如果需要 system prompt，勾选“系统提示词模式”
8. 点击“校验样本”
9. 点击“保存 JSONL”

## 说明

- 工具会校验 `text_info` 中的标签是否按 `mask` / `no_mask` 交替出现
- 媒体项统一使用字段名 `image_url`，与示例数据格式保持一致
- 当前视频采用路径管理和外部打开方式，不提供内嵌播放器
- 远程 URL 可以保存，但当前不会下载后做内嵌预览
- 图片缩略图和大图预览建议安装 `pillow`，否则只能预览部分格式
