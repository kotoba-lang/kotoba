from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5221_classify(**kwargs: Any) -> dict[str, Any]:
    """Service activities incidental to land transportation

    This class includes activities supporting land transport.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5221":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5221."}
    return await task_open_isic_classify_entity(**kwargs)
