from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6202_classify(**kwargs: Any) -> dict[str, Any]:
    """Computer consultancy and computer facilities management activities.

    This class includes the provision of computer consultancy and management of computer facilities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6202":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6202."}
    return await task_open_isic_classify_entity(**kwargs)
