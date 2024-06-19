from src.main import ChannelTranscriptor
import argparse
import asyncio


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="URL of the channel")
    parser.add_argument("--output_dir", help="Output directory")

    # add optional arguments
    parser.add_argument(
        "--batch",
        help="Batch size in which video streams will be downloaded",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--background_processes",
        help="Number of background processes in which transcriptions will be running",
        type=int,
        default=3,
    )

    args = parser.parse_args()

    await ChannelTranscriptor(
        url=args.url,
        output_dir=args.output_dir,
        batch=args.batch,
        background_processes=args.background_processes,
    ).transcribe()


if __name__ == "__main__":
    asyncio.run(main())
