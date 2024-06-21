import os
from src.service import StreamFetcher, Transcriptor
from rich.progress import Progress


class ChannelTranscriptor:
    def __init__(
        self,
        url: str,
        output_dir: str,
        model: str,
        batch: int = 5,
        background_processes: int = 3,
    ):
        self._pbar = None
        self.fetcher = StreamFetcher(url, batch)
        output_dir = self._output_dir(self.fetcher.channel.channel_id, output_dir)

        self.transcriptor = Transcriptor(output_dir, model, background_processes)

    def _output_dir(self, channel_id: str, output_dir: str) -> str:
        """Create output directory for the channel videos

        Args:
            channel_id (str): Channel id
            output_dir (str): Output directory
        """

        _dir = f"{output_dir.rstrip('/')}/{channel_id}/"
        if not os.path.exists(_dir):
            os.makedirs(_dir)

        return _dir

    async def transcribe(self):
        """Transcribe the channel videos"""

        try:
            self._pbar = Progress(expand=True)
            self._pbar.start()

            with self.transcriptor.start(self._pbar) as transcriptor:
                async for _id, stream, total_items in self.fetcher.list(self._pbar):
                    transcriptor.transcribe_async(stream, _id, total_items)
        finally:
            if self._pbar:
                self._pbar.finish()
                self._pbar = None
