"""
NLP worker — handles BOTH nlp_processing AND grammar_correction tasks.

Both stages pull from stream:tasks:nlp. The worker dispatches to the
correct stage module based on stage_name in the Redis message.
This demonstrates that a single worker pool can serve multiple stage types
when they share infrastructure characteristics (fast, CPU-bound).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from workers.base_worker import BaseWorker
from workers.stages import nlp_stage, grammar_stage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


class NLPWorker(BaseWorker):
    stage_name = "nlp_processing"   # used for worker registration + heartbeat type

    def _handles_stage(self, stage_name: str) -> bool:
        return stage_name in ("nlp_processing", "grammar_correction")

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        # Dispatched by _process_message via stage_name from message data
        # This method is called with the correct stage context
        raise NotImplementedError("Use execute_for_stage instead")

    async def _execute_for_stage(
        self, stage_name: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        if stage_name == "grammar_correction":
            return grammar_stage.run(input_data)
        return nlp_stage.run(input_data)

    async def _process_message(self, msg_id: str, data: dict[str, str]) -> None:
        """Override to dispatch to the right stage module."""
        task_stage = data.get("stage_name", "")
        if not self._handles_stage(task_stage):
            await self.redis.xack(self.stream_name, self.CONSUMER_GROUP_NAME, msg_id)
            return

        # Temporarily override execute to dispatch correctly
        stage_name_backup = self.stage_name
        try:
            self._current_stage = task_stage
            await super()._process_message(msg_id, data)
        finally:
            self._current_stage = None

    # Patch: override execute to dispatch based on current stage
    # We store the current stage name during _process_message execution
    _current_stage: str | None = None

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        stage = self._current_stage or "nlp_processing"
        if stage == "grammar_correction":
            return grammar_stage.run(input_data)
        return nlp_stage.run(input_data)


if __name__ == "__main__":
    asyncio.run(NLPWorker().start())
