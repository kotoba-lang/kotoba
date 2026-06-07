from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4781_classify(**kwargs: Any) -> dict[str, Any]:
    """Retail sale via stalls and markets of food, beverages and tobacco products.

    This class includes the retail sale of food, beverages and tobacco via market stalls and similar selling points.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4781":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4781."}
    return await task_open_isic_classify_entity(**kwargs)
