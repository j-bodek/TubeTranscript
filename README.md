## YouTube Transcription

Simple cli tool to download all videos from a YouTube channel and transcribe them to text
using the OpenAI whisper model.

### Installation

```bash
# clone repository
git clone ...
# create a virtual environment
python -m venv env
source env/bin/activate
# install requirements
pip install -r requirements.txt
```

### Usage

```bash
python main.py --url <channel_id> --output_dir <output_dir>

options:
  -h, --help            show this help message and exit
  --url URL             URL of the channel
  --output_dir OUTPUT_DIR
                        Output directory
  --model {tiny,base,small,medium,large}
                        Transcription model to use. Check https://github.com/openai/whisper?tab=readme-ov-file#available-models-and-languages
  --batch BATCH         Batch size in which video streams will be downloaded
  --background_processes BACKGROUND_PROCESSES
                        Number of background processes in which transcriptions will be running
```
