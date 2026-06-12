from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0162_classify(**kwargs: Any) -> dict[str, Any]:
    """Support activities for animal production.

    This class includes support activities to animal production carried out on a fee or contract basis.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0162":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0162."}
    return await task_open_isic_classify_entity(**kwargs)
