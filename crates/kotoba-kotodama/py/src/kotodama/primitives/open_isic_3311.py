from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3311_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of fabricated metal products.

    This class includes the repair and maintenance of fabricated metal products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3311":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3311."}
    return await task_open_isic_classify_entity(**kwargs)
