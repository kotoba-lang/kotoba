from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9101_classify(**kwargs: Any) -> dict[str, Any]:
    """Library and archive activities

    This class includes the provision of library and archive services.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9101":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9101."}
    return await task_open_isic_classify_entity(**kwargs)
