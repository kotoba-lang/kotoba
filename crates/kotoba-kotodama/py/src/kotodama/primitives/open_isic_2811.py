from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2811_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of engines and turbines, except aircraft, vehicle and cycle engines.

    This class includes the manufacture of engines and turbines, except aircraft propulsion engines, motor vehicle engines and motorcycle engines.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2811":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2811."}
    return await task_open_isic_classify_entity(**kwargs)
