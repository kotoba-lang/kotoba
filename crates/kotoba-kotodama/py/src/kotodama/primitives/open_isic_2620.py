from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2620_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of computers and peripheral equipment.

    This class includes the manufacture of and/or assembly of electronic computers and computer peripheral equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2620":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2620."}
    return await task_open_isic_classify_entity(**kwargs)
