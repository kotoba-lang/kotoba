from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9511_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of computers and peripheral equipment

    This class includes the repair and maintenance of computers and peripheral equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9511":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9511."}
    return await task_open_isic_classify_entity(**kwargs)
