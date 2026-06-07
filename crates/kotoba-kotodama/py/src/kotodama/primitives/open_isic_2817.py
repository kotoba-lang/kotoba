from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2817_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of office machinery and equipment (except computers and peripheral equipment).

    This class includes the manufacture of office machinery and equipment, excluding computers and computer peripheral equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2817":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2817."}
    return await task_open_isic_classify_entity(**kwargs)
