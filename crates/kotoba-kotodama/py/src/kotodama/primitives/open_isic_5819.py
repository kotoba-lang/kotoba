from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5819_classify(**kwargs: Any) -> dict[str, Any]:
    """Other publishing activities

    This class includes the publishing of other items not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5819":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5819."}
    return await task_open_isic_classify_entity(**kwargs)
