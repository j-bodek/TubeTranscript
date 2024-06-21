from dataclasses import dataclass
import pytube
from enum import StrEnum


class TranscriptionModel(StrEnum):
    tiny = "tiny"
    base = "base"
    small = "small"
    medium = "medium"
    large = "large"


@dataclass
class TranscriptionMsg:
    video_id: str
    stream: pytube.Stream
