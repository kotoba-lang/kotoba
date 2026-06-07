from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5222_classify(**kwargs: Any) -> dict[str, Any]:
    """Service activities incidental to water transportation

    This class includes activities supporting water transport.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5222":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5222."}
    return await task_open_isic_classify_entity(**kwargs)
