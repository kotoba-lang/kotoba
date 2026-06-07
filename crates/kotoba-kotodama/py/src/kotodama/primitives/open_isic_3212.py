from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3212_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of imitation jewellery and related articles.

    This class includes the manufacture of jewellery and related articles of base metals plated with precious metals or other materials.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3212":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3212."}
    return await task_open_isic_classify_entity(**kwargs)
