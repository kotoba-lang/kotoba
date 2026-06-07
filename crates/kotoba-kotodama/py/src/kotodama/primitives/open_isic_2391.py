from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2391_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of refractory products

    This class includes the manufacture of refractory ceramic goods.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2391":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2391."}
    return await task_open_isic_classify_entity(**kwargs)
