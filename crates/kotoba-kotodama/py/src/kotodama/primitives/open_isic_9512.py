from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9512_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of communication equipment

    This class includes the repair and maintenance of communication equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9512":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9512."}
    return await task_open_isic_classify_entity(**kwargs)
