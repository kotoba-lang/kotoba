from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6209_classify(**kwargs: Any) -> dict[str, Any]:
    """Other information technology and computer service activities.

    This class includes other IT and computer service activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6209":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6209."}
    return await task_open_isic_classify_entity(**kwargs)
