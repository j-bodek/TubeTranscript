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

logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.ERROR)


class VideoFetcher:
    def __init__(self, url: str, queue: Queue, timeout: int = 60 * 60):
        self.channel = pytube.Channel(url)
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
        self.url = url
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

        with VideoFetcher(self.url, self._videos).run_async() as video_fetcher:

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
    pass
