from dataclasses import dataclass
import pytube


@dataclass
class TranscriptionMsg:
    video_id: str
    stream: pytube.Stream
