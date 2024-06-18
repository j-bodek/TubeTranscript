from os import path
import os
import logging
from src.service import YoutubeCrawler, Transcriptor

logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.ERROR)


class ChannelTranscriptor:
    def __init__(
        self, url: str, output_dir: str, batch: int = 5, background_processes: int = 3
    ):
        self.crawler = YoutubeCrawler(url, batch)
        output_dir = self._output_dir(self.crawler.channel.channel_id, output_dir)

        self.transcriptor = Transcriptor(output_dir, background_processes)

    def _output_dir(self, channel_id: str, output_dir: str) -> str:
        _dir = f"{output_dir.rstrip('/')}/{channel_id}/"
        if not path.exists(_dir):
            os.makedirs(_dir)

        return _dir

    async def transcribe(self):
        with self.transcriptor.start() as transcriptor:
            async for _id, stream in self.crawler.list():
                transcriptor.transcribe_async(stream, _id)
