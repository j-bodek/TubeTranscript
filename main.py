import pytube
from anyio import to_thread
import time
import asyncio
import speech_recognition as sr
from os import path
from pydub import AudioSegment
import os
import tempfile
from typing import AsyncGenerator
import logging

logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.ERROR)


async def download_file(stream, output_path):
    return await to_thread.run_sync(_download_file, stream, output_path)


def _download_file(stream, output_path):
    with tempfile.NamedTemporaryFile(
        suffix=f".{stream.subtype}", delete=True
    ) as og_file:
        stream.download(filename=og_file.name)
        sound = AudioSegment.from_file(og_file.name)

        with tempfile.NamedTemporaryFile(
            suffix=f".{stream.subtype}", delete=True
        ) as audio_file:

            sound.export(audio_file.name, format="wav")

            r = sr.Recognizer()
            with sr.AudioFile(audio_file.name) as source:
                audio = r.record(source)
                try:
                    text = r.recognize_whisper(audio)
                    with open(output_path, "w") as f:
                        f.write(text)

                except sr.exceptions.TranscriptionFailed as e:
                    print("Transcription failed")
                except Exception as e:
                    print(f"Error while transcribing - {e}")


class ChannelCrawler:
    def __init__(
        self, url: str, output_dir: str, batch: int = 5, background_processes: int = 3
    ):
        self.channel = pytube.Channel(url)
        self.batch = batch
        self.output_dir = self._output_dir(output_dir)
        self.background_processes = background_processes

    def _output_dir(self, output_dir: str) -> str:
        _dir = f"{output_dir.rstrip('/')}/{self.channel.channel_id}/"
        if not path.exists(_dir):
            os.makedirs(_dir)

        return _dir

    async def crawl(self):
        tasks = []
        async for _id, stream in self.list():

            tasks.append(
                download_file(stream, output_path=f"{self.output_dir}{_id}.txt")
            )

            if len(tasks) == self.background_processes:
                await asyncio.gather(*tasks)
                tasks = []

        if len(tasks):
            await asyncio.gather(*tasks)

    async def list(self) -> AsyncGenerator[str, pytube.Stream]:
        """Generate ids and streams urls of the channel videos"""
        tasks = []
        for video in self.channel.videos:
            tasks.append(self.get_stream(video))
            if len(tasks) == self.batch:
                for _id, stream in await asyncio.gather(*tasks):
                    if not stream:
                        continue

                    yield _id, stream

                tasks = []

        if tasks:
            for _id, stream in await asyncio.gather(*tasks):
                if not stream:
                    continue

                yield _id, stream

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


async def main():
    url = "https://www.youtube.com/@squewe"

    crawler = ChannelCrawler(url, output_dir="files/")
    await crawler.crawl()


if __name__ == "__main__":
    asyncio.run(main())
