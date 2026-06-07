from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3821_classify(**kwargs: Any) -> dict[str, Any]:
    """Treatment and disposal of non-hazardous waste.

    This class includes the treatment and disposal of non-hazardous waste.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3821":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3821."}
    return await task_open_isic_classify_entity(**kwargs)
