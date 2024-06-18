# from src.main import ChannelTranscriptor
from src.service import YoutubeCrawler
import asyncio


async def main():
    url = "https://www.youtube.com/@squewe"

    # await ChannelTranscriptor(url, output_dir="files/").transcribe()
    async for _id, stream in YoutubeCrawler(url).list():
        pass


if __name__ == "__main__":
    asyncio.run(main())
