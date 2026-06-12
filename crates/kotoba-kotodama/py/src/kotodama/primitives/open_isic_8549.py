from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8549_classify(**kwargs: Any) -> dict[str, Any]:
    """Other education n.e.c.

    This class includes education not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8549":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8549."}
    return await task_open_isic_classify_entity(**kwargs)
