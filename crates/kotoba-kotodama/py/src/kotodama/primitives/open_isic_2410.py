from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2410_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of basic iron and steel.

    This class includes the manufacture of basic iron and steel and ferro-alloys.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2410":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2410."}
    return await task_open_isic_classify_entity(**kwargs)
