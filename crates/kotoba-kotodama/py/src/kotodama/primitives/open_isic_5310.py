from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5310_classify(**kwargs: Any) -> dict[str, Any]:
    """Postal activities

    This class includes postal activities undertaken under a universal service obligation.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5310":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5310."}
    return await task_open_isic_classify_entity(**kwargs)
