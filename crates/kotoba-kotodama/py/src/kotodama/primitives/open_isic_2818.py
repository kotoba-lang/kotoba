from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2818_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of power-driven hand tools.

    This class includes the manufacture of power-driven hand tools.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2818":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2818."}
    return await task_open_isic_classify_entity(**kwargs)
