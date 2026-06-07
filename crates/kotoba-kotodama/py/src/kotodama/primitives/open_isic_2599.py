from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2599_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other fabricated metal products n.e.c..

    This class includes the manufacture of a variety of fabricated metal products not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2599":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2599."}
    return await task_open_isic_classify_entity(**kwargs)
