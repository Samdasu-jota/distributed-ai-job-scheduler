"""
Diagnostics worker — fan-in stage.

This worker handles the most architecturally interesting task: it only
runs after BOTH nlp_processing AND natural_phrasing have completed.
The scheduler enforces this via depends_on in the tasks table.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from workers.base_worker import BaseWorker
from workers.stages import diagnostics_stage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


class DiagnosticsWorker(BaseWorker):
    stage_name = "diagnostics"

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        # input_data is the merged result from nlp_processing + natural_phrasing
        # (plus all upstream stages — audio, stt, grammar — via the merge chain)
        return diagnostics_stage.run(input_data)


if __name__ == "__main__":
    asyncio.run(DiagnosticsWorker().start())
