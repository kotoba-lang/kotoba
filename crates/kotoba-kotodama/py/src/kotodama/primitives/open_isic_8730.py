from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8730_classify(**kwargs: Any) -> dict[str, Any]:
    """Residential care activities for the elderly and disabled

    This class includes the provision of residential and personal care services for the elderly and disabled who are unable to fully care for themselves.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8730":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8730."}
    return await task_open_isic_classify_entity(**kwargs)
