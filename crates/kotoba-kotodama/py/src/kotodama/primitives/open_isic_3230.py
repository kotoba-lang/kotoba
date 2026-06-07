from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3230_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of sports goods.

    This class includes the manufacture of sporting and athletic goods (except apparel and footwear).
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3230":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3230."}
    return await task_open_isic_classify_entity(**kwargs)
