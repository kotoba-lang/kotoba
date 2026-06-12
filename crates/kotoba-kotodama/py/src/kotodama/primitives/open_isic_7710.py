from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7710_classify(**kwargs: Any) -> dict[str, Any]:
    """Renting and leasing of motor vehicles

    This class includes the renting and operational leasing of automobiles and other motor vehicles without a driver.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7710":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7710."}
    return await task_open_isic_classify_entity(**kwargs)
