import speech_recognition as sr
from pydub import AudioSegment
import tempfile


def download_file(stream, output_path):
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
