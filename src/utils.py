from contextlib import contextmanager
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import pytube
from src.logger import logger


@contextmanager
def export_audio(stream: pytube.Stream) -> str:
    """Download the stream and export it to a temporary audio file

    Args:
        stream (pytube.Stream): Video stream
    """

    try:
        with tempfile.NamedTemporaryFile(
            suffix=f".{stream.subtype}", delete=True
        ) as og_file:
            stream.download(filename=og_file.name)
            sound = AudioSegment.from_file(og_file.name)

            with tempfile.NamedTemporaryFile(
                suffix=f".{stream.subtype}", delete=True
            ) as audio_file:
                sound.export(audio_file.name, format="wav")
                yield audio_file.name
    finally:
        pass


def transcribe_stream(
    stream: pytube.Stream,
    output_path: str,
    retry: int = 2,
):
    """Download the stream and transcribe it to text

    Args:
        stream (pytube.Stream): Video stream
        output_path (str): Output path
    """

    with export_audio(stream) as audio_file_name:

        r = sr.Recognizer()

        for i in range(retry + 1):
            try:
                with sr.AudioFile(audio_file_name) as source:
                    audio = r.record(source)

                    text = r.recognize_whisper(audio)
                    with open(output_path, "w") as f:
                        f.write(text)
                    break
            except Exception as e:
                if i == retry:
                    raise e

                logger.error(f"Error while transcribing - {e}, retrying...")
