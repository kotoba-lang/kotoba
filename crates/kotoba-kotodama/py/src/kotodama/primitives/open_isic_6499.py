from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6499_classify(**kwargs: Any) -> dict[str, Any]:
    """Other financial service activities, except insurance and pension funding n.e.c..

    This class includes other financial service activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6499":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6499."}
    return await task_open_isic_classify_entity(**kwargs)
