from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2920_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of bodies (coachwork) for motor vehicles; manufacture of trailers and semi-trailers.

    This class includes the manufacture of bodies for motor vehicles and the manufacture of trailers and semi-trailers.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2920":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2920."}
    return await task_open_isic_classify_entity(**kwargs)
