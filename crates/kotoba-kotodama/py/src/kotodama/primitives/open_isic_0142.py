from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0142_classify(**kwargs: Any) -> dict[str, Any]:
    """Raising of horses and other equines.

    This class includes raising and breeding of horses, asses, mules or hinnies, and production of raw equine milk and equine semen.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0142":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0142."}
    return await task_open_isic_classify_entity(**kwargs)
