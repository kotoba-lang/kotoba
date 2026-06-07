from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7722_classify(**kwargs: Any) -> dict[str, Any]:
    """Renting of video tapes and disks

    This class includes the renting of video tapes, DVDs and similar audio and video recordings.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7722":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7722."}
    return await task_open_isic_classify_entity(**kwargs)
