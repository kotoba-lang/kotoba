from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4661_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of solid, liquid and gaseous fuels and related products

    This class includes the wholesale of fuels and related products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4661":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4661."}
    return await task_open_isic_classify_entity(**kwargs)
