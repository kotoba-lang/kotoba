from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7010_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of head offices

    This class includes the overseeing and managing of other units of the company or enterprise; undertaking the strategic or organizational planning and decision making role of the company or enterprise.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7010":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7010."}
    return await task_open_isic_classify_entity(**kwargs)
