from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2825_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of machinery for food, beverage and tobacco processing.

    This class includes the manufacture of machinery used in the processing of food, beverages and tobacco.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2825":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2825."}
    return await task_open_isic_classify_entity(**kwargs)
