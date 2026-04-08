from dataclasses import dataclass, field


TAG_VALUES = ("mask", "no_mask")
MEDIA_LABELS = {"image": "图片", "video": "视频"}
LABEL_TO_MEDIA = {v: k for k, v in MEDIA_LABELS.items()}


@dataclass
class TextItem:
    text: str = ""
    tag: str = "mask"

    def to_dict(self):
        return {"text": self.text, "tag": self.tag}


@dataclass
class MediaItem:
    media_url: str = ""
    matched_text_index: int = 0

    def to_dict(self):
        return {"image_url": self.media_url, "matched_text_index": self.matched_text_index}


@dataclass
class Sample:
    media_type: str = "image"
    is_system: int = 0
    text_info: list[TextItem] = field(default_factory=list)
    media_info: list[MediaItem] = field(default_factory=list)

    def to_dict(self):
        key = "image_info" if self.media_type == "image" else "video_info"
        data = {"text_info": [i.to_dict() for i in self.text_info], key: [i.to_dict() for i in self.media_info]}
        if self.is_system:
            data["is_system"] = 1
        return data

    @classmethod
    def from_dict(cls, data):
        key = "image_info" if data.get("image_info") is not None else "video_info"
        return cls(
            media_type="image" if key == "image_info" else "video",
            is_system=1 if data.get("is_system") else 0,
            text_info=[TextItem(i.get("text", ""), i.get("tag", "mask")) for i in data.get("text_info", [])],
            media_info=[MediaItem(i.get("image_url", ""), int(i.get("matched_text_index", 0))) for i in data.get(key, [])],
        )
