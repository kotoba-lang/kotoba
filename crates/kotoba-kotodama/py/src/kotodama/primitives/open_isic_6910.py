from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6910_classify(**kwargs: Any) -> dict[str, Any]:
    """Legal activities.

    This class includes legal representation of one party's interest against another party, whether or not before courts or other judicial bodies.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6910":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6910."}
    return await task_open_isic_classify_entity(**kwargs)
