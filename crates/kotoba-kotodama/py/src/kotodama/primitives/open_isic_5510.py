from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5510_classify(**kwargs: Any) -> dict[str, Any]:
    """Short-term accommodation activities

    This class includes the provision of short-stay accommodation for visitors.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5510":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5510."}
    return await task_open_isic_classify_entity(**kwargs)
