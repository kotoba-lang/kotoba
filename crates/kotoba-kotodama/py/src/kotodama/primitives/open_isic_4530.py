from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4530_classify(**kwargs: Any) -> dict[str, Any]:
    """Sale of motor vehicle parts and accessories

    This class includes the wholesale and retail sale of all kinds of parts, components, supplies, tools and accessories for motor vehicles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4530":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4530."}
    return await task_open_isic_classify_entity(**kwargs)
