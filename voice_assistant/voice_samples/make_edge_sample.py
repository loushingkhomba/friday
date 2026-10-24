"""Generate a sample of Friday's former online Edge Ava voice."""

import asyncio
from pathlib import Path

from edge_tts import Communicate


OUTPUT = Path(__file__).resolve().parent / "edge_ava_neural.mp3"
TEXT = "Hello the user. I'm Friday, here and ready to help. What would you like to do today?"


async def main() -> None:
    await Communicate(TEXT, voice="en-US-AvaNeural", rate="+0%").save(str(OUTPUT))
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
