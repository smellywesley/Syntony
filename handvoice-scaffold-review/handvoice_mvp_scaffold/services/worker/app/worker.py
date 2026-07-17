from __future__ import annotations

import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("handvoice.worker")


def main() -> None:
    logger.info("HandVoice worker scaffold started")
    logger.info("Queue integration is intentionally left provider-neutral")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
