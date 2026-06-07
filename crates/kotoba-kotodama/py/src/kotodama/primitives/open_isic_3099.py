from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3099_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other transport equipment n.e.c..

    This class includes the manufacture of transport equipment not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3099":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3099."}
    return await task_open_isic_classify_entity(**kwargs)
