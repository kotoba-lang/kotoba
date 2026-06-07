from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8020_classify(**kwargs: Any) -> dict[str, Any]:
    """Security systems service activities

    This class includes the selling, installing, repairing and maintaining of security systems such as burglar and fire alarms.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8020":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8020."}
    return await task_open_isic_classify_entity(**kwargs)
