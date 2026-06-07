from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3091_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of motorcycles.

    This class includes the manufacture of motorcycles, mopeds and motorised cycles of all kinds.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3091":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3091."}
    return await task_open_isic_classify_entity(**kwargs)
