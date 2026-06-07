from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3299_classify(**kwargs: Any) -> dict[str, Any]:
    """Other manufacturing n.e.c..

    This class includes the manufacture of various products not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3299":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3299."}
    return await task_open_isic_classify_entity(**kwargs)
