from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5820_classify(**kwargs: Any) -> dict[str, Any]:
    """Software publishing

    This class includes the publishing of ready-made (non-customised) software.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5820":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5820."}
    return await task_open_isic_classify_entity(**kwargs)
