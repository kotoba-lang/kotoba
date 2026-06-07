from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9522_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of household appliances and home and garden equipment

    This class includes the repair and maintenance of household appliances and home and garden equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9522":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9522."}
    return await task_open_isic_classify_entity(**kwargs)
