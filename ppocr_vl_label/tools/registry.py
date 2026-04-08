from .base import AnnotationToolSpec


DEFAULT_TOOL_ID = "sft_vl"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, AnnotationToolSpec] = {}

    def register(self, spec: AnnotationToolSpec):
        self._tools[spec.tool_id] = spec

    def get(self, tool_id: str) -> AnnotationToolSpec:
        if tool_id not in self._tools:
            raise KeyError(f"未知标注工具：{tool_id}")
        return self._tools[tool_id]

    def list_tools(self):
        return list(self._tools.values())


_registry = ToolRegistry()
_registry.register(
    AnnotationToolSpec(
        tool_id=DEFAULT_TOOL_ID,
        name="SFT VL 标注工具",
        description="面向 SFT VL 数据集的多模态样本标注工具。",
        app_path="ppocr_vl_label.app_window:App",
    )
)


def get_tool_registry():
    return _registry
