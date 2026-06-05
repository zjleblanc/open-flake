import logging
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger("openflake.events")


class RecordEvent(BaseModel):
    action: Literal["create", "update", "delete"]
    table: str
    sys_id: str
    record: dict


_subscribers: list = []


def subscribe(callback) -> None:
    _subscribers.append(callback)


async def emit(event: RecordEvent) -> None:
    logger.info(
        "record_event",
        extra={
            "action": event.action,
            "table": event.table,
            "sys_id": event.sys_id,
        },
    )
    for callback in _subscribers:
        try:
            result = callback(event)
            if hasattr(result, "__await__"):
                await result
        except Exception:
            logger.exception("event subscriber failed")
