"""Aggregation worker — terminal DAG stage."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from workers.base_worker import BaseWorker
from workers.stages import aggregation_stage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


class AggregationWorker(BaseWorker):
    stage_name = "aggregation"

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return aggregation_stage.run(input_data)


if __name__ == "__main__":
    asyncio.run(AggregationWorker().start())
