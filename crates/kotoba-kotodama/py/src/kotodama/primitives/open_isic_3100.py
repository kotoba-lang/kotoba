from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3100_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of furniture.

    This class includes the manufacture of furniture and related products of any material.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3100":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3100."}
    return await task_open_isic_classify_entity(**kwargs)
