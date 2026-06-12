from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3520_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of gas; distribution of gaseous fuels through mains.

    This class includes the manufacture of gas and the distribution of gaseous fuels through a system of mains.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3520":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3520."}
    return await task_open_isic_classify_entity(**kwargs)
