from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3822_classify(**kwargs: Any) -> dict[str, Any]:
    """Treatment and disposal of hazardous waste.

    This class includes the treatment and disposal of hazardous waste.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3822":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3822."}
    return await task_open_isic_classify_entity(**kwargs)
