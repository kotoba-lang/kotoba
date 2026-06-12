from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2021_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of pesticides and other agrochemical products

    This class includes the manufacture of pesticides and other agrochemical products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2021":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2021."}
    return await task_open_isic_classify_entity(**kwargs)
