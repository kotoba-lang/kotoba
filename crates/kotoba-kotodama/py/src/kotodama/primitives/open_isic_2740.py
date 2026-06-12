from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2740_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of electric lighting equipment.

    This class includes the manufacture of electric light bulbs and tubes and other illumination equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2740":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2740."}
    return await task_open_isic_classify_entity(**kwargs)
