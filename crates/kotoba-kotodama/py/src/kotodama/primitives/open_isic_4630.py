from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4630_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of food, beverages and tobacco

    This class includes the wholesale of food, beverages and tobacco products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4630":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4630."}
    return await task_open_isic_classify_entity(**kwargs)
