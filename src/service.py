import pytube
import logging
from anyio import to_thread
import time
from tqdm.asyncio import tqdm
import asyncio
from typing import AsyncGenerator, Callable
from queue import Queue
from multiprocessing import pool
from contextlib import contextmanager
from src.utils import download_file
from src.schemas import TranscriptionMsg

logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.ERROR)


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
        """Generate ids and streams urls of the channel videos"""

        for video in self.channel.videos:
            self._total += 1
            self._queue.put(video, timeout=self._timeout)


class YoutubeCrawler:
    def __init__(self, url: str, batch: int = 5):
        self.channel = pytube.Channel(url)
        self.batch = batch

        self._videos = Queue(maxsize=10000)
        self._total_videos: int = 0

    async def get_stream(self, video) -> tuple[str, pytube.Stream]:
        return await to_thread.run_sync(self._get_stream, video)

    @staticmethod
    def _get_stream(video) -> tuple[str, pytube.Stream]:
        for i in range(1, 4):
            try:
                streams = video.streams
                stream = streams.get_audio_only() or streams.first()
                return video.video_id, stream
            except Exception as e:
                logging.error(f"Error getting video {video.video_id} - {e}")

            if i != 2:
                # add exponential backoff
                time.sleep(2**i)

        return None, None

    async def list(self) -> AsyncGenerator[str, pytube.Stream]:
        """Generate ids and streams urls of the channel videos"""

        with VideoFetcher(self.channel, self._videos).run_async() as video_fetcher:

            tasks, pbar = [], tqdm(total=video_fetcher._total, desc="Fetching videos")

            while video_fetcher.running or self._videos.qsize() > 0:
                if self._videos.qsize() == 0:
                    await asyncio.sleep(0.1)
                    continue

                if pbar.total != video_fetcher._total:
                    pbar.total = video_fetcher._total
                    pbar.refresh()

                video = self._videos.get()
                tasks.append(self.get_stream(video))
                pbar.update(1)

                if len(tasks) == self.batch or self._videos.qsize() == 0:
                    for _id, stream in await asyncio.gather(*tasks):
                        if not stream:
                            continue

                        yield _id, stream

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

    def _get_output_path(self, _id: str) -> str:
        return f"{self.output_dir}{_id}.txt"

    def _error_callback(self, e: Exception, *args, **kwargs):
        logging.error(f"Error while transcribing - {e}")
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

    @contextmanager
    def start(self):
        try:
            self._running = True
            yield self
        finally:
            self._pool.close()
            self._pool.join()
            self._running = False

    def transcribe_async(self, stream: pytube.Stream, _id: str):
        msg = TranscriptionMsg(video_id=_id, stream=stream)
        self._queue.put(msg, timeout=self._timeout)

        if self._tasks < self._pool._processes:
            # print("PUTTING TO WORKER ", self._tasks)
            self._run_transcription_worker()
