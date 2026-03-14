"""Speech-to-text worker."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from workers.base_worker import BaseWorker
from workers.stages import stt_stage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


class STTWorker(BaseWorker):
    stage_name = "speech_to_text"

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return stt_stage.run(input_data)


if __name__ == "__main__":
    asyncio.run(STTWorker().start())
