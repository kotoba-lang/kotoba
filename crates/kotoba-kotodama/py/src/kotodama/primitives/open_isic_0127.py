from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0127_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of beverage crops

    This class includes the growing of beverage crops.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0127":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0127."}
    return await task_open_isic_classify_entity(**kwargs)
