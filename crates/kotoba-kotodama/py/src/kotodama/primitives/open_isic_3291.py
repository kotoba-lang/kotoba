from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3291_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of brooms and brushes.

    This class includes the manufacture of brooms, brushes, mops and similar articles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3291":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3291."}
    return await task_open_isic_classify_entity(**kwargs)
