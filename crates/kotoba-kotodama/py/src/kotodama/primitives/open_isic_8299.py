from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8299_classify(**kwargs: Any) -> dict[str, Any]:
    """Other business support service activities n.e.c.

    This class includes miscellaneous business support activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8299":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8299."}
    return await task_open_isic_classify_entity(**kwargs)
