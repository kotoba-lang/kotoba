from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1820_classify(**kwargs: Any) -> dict[str, Any]:
    """Reproduction of recorded media

    This class includes the reproduction from master copies of gramophone records, compact discs, video recordings, software and other recorded media.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1820":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1820."}
    return await task_open_isic_classify_entity(**kwargs)
