from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3292_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of hard surface floor coverings.

    This class includes the manufacture of non-textile floor coverings.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3292":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3292."}
    return await task_open_isic_classify_entity(**kwargs)
