from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2640_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of consumer electronics.

    This class includes the manufacture of electronic audio and video equipment for consumers.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2640":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2640."}
    return await task_open_isic_classify_entity(**kwargs)
