from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5223_classify(**kwargs: Any) -> dict[str, Any]:
    """Service activities incidental to air transportation

    This class includes activities supporting air transport.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5223":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5223."}
    return await task_open_isic_classify_entity(**kwargs)
