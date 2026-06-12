from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5320_classify(**kwargs: Any) -> dict[str, Any]:
    """Courier activities

    This class includes pick-up and delivery of letters and parcels without a universal service obligation.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5320":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5320."}
    return await task_open_isic_classify_entity(**kwargs)
