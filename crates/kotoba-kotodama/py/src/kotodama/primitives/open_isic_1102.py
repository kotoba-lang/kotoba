from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1102_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of wines

    This class includes the manufacture of wine and other fermented beverages made from grapes and other fruits.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1102":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1102."}
    return await task_open_isic_classify_entity(**kwargs)
