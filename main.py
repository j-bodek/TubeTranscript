import pytube
from anyio import to_thread
import time
import asyncio
import speech_recognition as sr
from os import path
from pydub import AudioSegment
import os
import tempfile


def _get_stream(video) -> tuple[str, str]:
    for i in range(1, 4):
        try:
            streams = video.streams
            stream = streams.get_audio_only() or streams.first()
            return stream, video.video_id
        except Exception as e:
            pass

        if i != 2:
            time.sleep(2**i)

    return None, None


async def get_stream(video) -> tuple[str, str]:
    return await to_thread.run_sync(_get_stream, video)


async def get_streams(channel):

    tasks = []
    for video in channel.videos:
        tasks.append(get_stream(video))
        if len(tasks) == 5:
            for url, _id in await asyncio.gather(*tasks):
                if not url:
                    continue

                yield url, _id

            tasks = []

    if tasks:
        for url, _id in await asyncio.gather(*tasks):
            if not url:
                continue

            yield url, _id


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


async def main():
    url = "https://www.youtube.com/@squewe"

    tasks = []
    channel = pytube.Channel(url)

    async for stream, _id in get_streams(channel):
        _dir = f"files/{channel.channel_id}/"
        if not path.exists(_dir):
            os.makedirs(_dir)

        tasks.append(download_file(stream, output_path=f"{_dir}{_id}.txt"))

        if len(tasks) == 3:
            await asyncio.gather(*tasks)
            tasks = []


if __name__ == "__main__":
    asyncio.run(main())
