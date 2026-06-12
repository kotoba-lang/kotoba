from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4510_classify(**kwargs: Any) -> dict[str, Any]:
    """Sale of motor vehicles

    This class includes the wholesale and retail sale of new and used vehicles: passenger motor vehicles, including specialized passenger motor vehicles such as ambulances and minibuses.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4510":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4510."}
    return await task_open_isic_classify_entity(**kwargs)
