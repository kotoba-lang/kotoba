from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8610_classify(**kwargs: Any) -> dict[str, Any]:
    """Hospital activities

    This class includes the provision of inpatient medical and surgical services.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8610":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8610."}
    return await task_open_isic_classify_entity(**kwargs)
