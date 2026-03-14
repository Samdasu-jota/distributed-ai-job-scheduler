"""Scheduler process entry point."""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    from shared.db import create_pool, close_pool
    from shared.redis_client import get_redis, close_redis, init_consumer_groups
    from scheduler.scheduler import Scheduler
    from scheduler.heartbeat_monitor import run_heartbeat_monitor

    poll_interval = float(os.getenv("SCHEDULER_POLL_INTERVAL", "2"))
    heartbeat_check_interval = 30.0

    logger.info("scheduler_starting", extra={"poll_interval": poll_interval})

    db = await create_pool()
    redis = await get_redis()
    await init_consumer_groups()

    scheduler = Scheduler(db=db, redis=redis, poll_interval=poll_interval)

    heartbeat_counter = 0

    try:
        while True:
            enqueued = await scheduler.run_once()
            if enqueued > 0:
                logger.info("scheduler_cycle", extra={"enqueued": enqueued})

            heartbeat_counter += 1
            # Run heartbeat monitor every ~30 seconds
            if heartbeat_counter * poll_interval >= heartbeat_check_interval:
                await run_heartbeat_monitor(db, redis)
                heartbeat_counter = 0

            await asyncio.sleep(poll_interval)

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("scheduler_stopping")
    finally:
        await close_pool()
        await close_redis()


if __name__ == "__main__":
    asyncio.run(main())
