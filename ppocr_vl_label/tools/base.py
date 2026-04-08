from dataclasses import dataclass
from importlib import import_module


@dataclass(frozen=True)
class AnnotationToolSpec:
    tool_id: str
    name: str
    description: str
    app_path: str

    def load_app_class(self):
        module_name, class_name = self.app_path.split(":")
        module = import_module(module_name)
        return getattr(module, class_name)

    def create_app(self, root):
        app_class = self.load_app_class()
        return app_class(root)
