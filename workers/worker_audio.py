"""Audio preprocessing worker."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from workers.base_worker import BaseWorker
from workers.stages import audio_stage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


class AudioWorker(BaseWorker):
    stage_name = "audio_preprocessing"

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return audio_stage.run(input_data)


if __name__ == "__main__":
    asyncio.run(AudioWorker().start())
