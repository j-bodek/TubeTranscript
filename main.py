from src.main import ChannelTranscriptor
import asyncio


async def main():
    url = "https://www.youtube.com/@squewe"

    await ChannelTranscriptor(url, output_dir="files/").transcribe()


if __name__ == "__main__":
    asyncio.run(main())
