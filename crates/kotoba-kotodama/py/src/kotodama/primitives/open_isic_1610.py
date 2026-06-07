from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1610_classify(**kwargs: Any) -> dict[str, Any]:
    """Sawmilling and planing of wood

    This class includes the sawing, planing and machining of wood into primary forms such as planks, beams and boards.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1610":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1610."}
    return await task_open_isic_classify_entity(**kwargs)
