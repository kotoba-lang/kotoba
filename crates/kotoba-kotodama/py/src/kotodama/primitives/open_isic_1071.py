from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1071_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of bakery products

    This class includes the manufacture of fresh, frozen or dry bakery products. It includes bread, rolls, biscuits, pies, cakes, pastries, waffles, pancakes and other similar baked goods.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1071":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1071."}
    return await task_open_isic_classify_entity(**kwargs)
