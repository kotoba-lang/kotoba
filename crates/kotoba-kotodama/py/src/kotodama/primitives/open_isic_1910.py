from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1910_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of coke oven products

    This class includes the manufacture of coke and coke oven products by the destructive distillation of coal.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1910":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1910."}
    return await task_open_isic_classify_entity(**kwargs)
