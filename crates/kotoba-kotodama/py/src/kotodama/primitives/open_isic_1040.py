from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1040_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of vegetable and animal oils and fats

    This class includes the manufacture of crude and refined oils and fats from vegetable or animal materials, except rendering or refining of lard and other edible animal fats.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1040":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1040."}
    return await task_open_isic_classify_entity(**kwargs)
