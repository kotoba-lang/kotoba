from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3211_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of jewellery and related articles.

    This class includes the manufacture of jewellery and related articles of precious metals and precious or semi-precious stones.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3211":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3211."}
    return await task_open_isic_classify_entity(**kwargs)
