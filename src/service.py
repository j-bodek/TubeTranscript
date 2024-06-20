import pytube
import logging
from anyio import to_thread
import time
import asyncio
from typing import AsyncGenerator, Callable
from queue import Queue
from threading import Lock
from multiprocessing import pool
from contextlib import contextmanager
from src.utils import download_file
from src.schemas import TranscriptionMsg
from rich.progress import Progress
from rich.logging import RichHandler

logging.basicConfig(level=logging.INFO, handlers=[RichHandler(level=logging.INFO)])
logging.basicConfig(level=logging.ERROR, handlers=[RichHandler(level=logging.ERROR)])
logger = logging.getLogger("rich")


class VideoFetcher:
    def __init__(self, channel: pytube.Channel, queue: Queue, timeout: int = 60 * 60):
        self.channel = channel
        self.running = False

        self._queue = queue
        self._timeout = timeout
        self._total = 0
        self._pool = pool.ThreadPool(1)

    @contextmanager
    def run_async(self, callback: Callable | None = None):
        """Run the fetcher in an async context manager

        Args:
            callback (Callable, optional): Callback function. Defaults to None.
        """

        try:
            self.running = True

            self._pool.apply_async(
                self._fetch,
                error_callback=self._callback(),
                callback=self._callback(callback),
            )
            yield self

        finally:
            self._pool.close()
            self._pool.join()
            self.running = False

    def _callback(self, callback: Callable | None = None):
        def _callback(*args, **kwargs):
            self.running = False

            if callback:
                callback(*args, **kwargs)

        return _callback

    def _fetch(self):
        """Get all video ids of the specified channel and put them into the queue"""

        for video in self.channel.videos:
            self._total += 1
            self._queue.put(video, timeout=self._timeout)


class StreamFetcher:
    def __init__(self, url: str, batch: int = 5):
        self.channel = pytube.Channel(url)
        self.batch = batch

        self._videos = Queue(maxsize=10000)

    async def get_stream(self, video: pytube.Video) -> tuple[str, pytube.Stream]:
        """Get the stream of the video - run in a separate thread

        Args:
            video (pytube.Video): Video object
        """

        return await to_thread.run_sync(self._get_stream, video)

    @staticmethod
    def _get_stream(video: pytube.Video) -> tuple[str, pytube.Stream]:
        """Get the stream of the video

        Args:
            video (pytube.Video): Video object
        """

        for i in range(1, 4):
            try:
                streams = video.streams
                stream = streams.get_audio_only() or streams.first()
                return video.video_id, stream
            except pytube.exceptions.VideoUnavailable as e:
                # skip video if it's unavailable
                logger.error(f"Video with id: {video.video_id} is unavailable - {e}")
            except Exception as e:
                logger.error(f"Error getting video {video.video_id} - {e}")
                if i != 3:
                    # add exponential backoff
                    time.sleep(2**i)

        return None, None

    async def list(self, pbar: Progress) -> AsyncGenerator[str, pytube.Stream]:
        """Generate ids and streams urls of the channel videos

        Args:
            pbar (Progress): Rich progress bar
        """

        with VideoFetcher(self.channel, self._videos).run_async() as video_fetcher:
            tasks, fetch_task = [], pbar.add_task(
                total=video_fetcher._total, description="Fetching videos"
            )

            while video_fetcher.running or self._videos.qsize() > 0:
                if self._videos.qsize() == 0:
                    await asyncio.sleep(0.1)
                    continue

                if pbar.tasks[fetch_task].total != video_fetcher._total:
                    pbar.update(fetch_task, total=video_fetcher._total)

                video = self._videos.get()
                tasks.append(self.get_stream(video))

                pbar.update(fetch_task, advance=1)

                if len(tasks) == self.batch or self._videos.qsize() == 0:
                    for _id, stream in await asyncio.gather(*tasks):
                        if not stream:
                            continue

                        yield _id, stream, video_fetcher._total

                    tasks = []


class Transcriptor:
    def __init__(
        self,
        output_dir: str,
        background_processes: int = 5,
        max_queuesize: int = 50,
        timeout: int = 60 * 60,
    ):
        self.output_dir = output_dir

        self._tasks = 0
        self._pool = pool.ThreadPool(processes=background_processes)
        self._queue = Queue(maxsize=max_queuesize)
        self._timeout = timeout
        self._running = False
        self._pbar = None
        self._transcription_task = None
        self._lock = Lock()

    def _get_output_path(self, _id: str) -> str:
        """Get the output path of the transcribed video

        Args:
            _id (str): Video id
        """

        return f"{self.output_dir}{_id}.txt"

    def _error_callback(self, e: Exception, *args, **kwargs):
        logger.error(f"Error while transcribing - {e}")
        self._tasks = max(0, self._tasks - 1)

    def _callback(self, *args, **kwargs):
        self._tasks -= max(0, self._tasks - 1)

    def _run_transcription_worker(self):
        self._pool.apply_async(
            self._transcription_worker,
            callback=self._callback,
            error_callback=self._error_callback,
        )
        self._tasks += 1

    def _transcription_worker(self):
        while True:
            if self._queue.empty():
                break

            msg = self._queue.get()
            download_file(msg.stream, self._get_output_path(msg.video_id))

            with self._lock:
                self._pbar.update(self._transcription_task, advance=1)

    @contextmanager
    def start(self, pbar: Progress):
        """Start transcription context manager

        Args:
            pbar (Progress): Rich progress bar
        """

        try:
            self._running = True
            self._pbar = pbar
            self._transcription_task = self._pbar.add_task(
                total=0, description="Transcribing videos"
            )

            yield self
        finally:
            self._pool.close()
            self._pool.join()
            self._running = False
            self._pbar = None

    def transcribe_async(self, stream: pytube.Stream, _id: str, total_items: int):
        """Transcribe the video asynchronously

        Args:
            stream (pytube.Stream): Video stream
            _id (str): Video id
            total_items (int): Total number of items
        """

        msg = TranscriptionMsg(video_id=_id, stream=stream)
        self._queue.put(msg, timeout=self._timeout)

        if (
            self._pbar is not None
            and self._pbar.tasks[self._transcription_task].total != total_items
        ):
            self._pbar.update(self._transcription_task, total=total_items)

        if self._tasks < self._pool._processes:
            self._run_transcription_worker()
