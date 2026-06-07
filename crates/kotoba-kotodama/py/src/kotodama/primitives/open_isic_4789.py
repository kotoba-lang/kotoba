from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4789_classify(**kwargs: Any) -> dict[str, Any]:
    """Retail sale via stalls and markets of other goods.

    This class includes the retail sale of other goods via market stalls and similar selling points.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4789":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4789."}
    return await task_open_isic_classify_entity(**kwargs)
