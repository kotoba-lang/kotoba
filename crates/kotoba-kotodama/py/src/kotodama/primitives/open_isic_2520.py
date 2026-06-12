from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2520_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of weapons and ammunition.

    This class includes the manufacture of military fighting vehicles, weapons and ammunition.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2520":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2520."}
    return await task_open_isic_classify_entity(**kwargs)
