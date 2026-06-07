from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2651_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of measuring, testing, navigating and control equipment.

    This class includes the manufacture of instruments and apparatus for measuring, testing, navigating and controlling.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2651":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2651."}
    return await task_open_isic_classify_entity(**kwargs)
