from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3040_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of military fighting vehicles.

    This class includes the manufacture of military fighting vehicles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3040":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3040."}
    return await task_open_isic_classify_entity(**kwargs)
