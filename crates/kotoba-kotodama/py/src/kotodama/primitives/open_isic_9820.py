from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9820_classify(**kwargs: Any) -> dict[str, Any]:
    """Undifferentiated service-producing activities of private households for own use

    This class includes the activities of private households that produce services for their own final consumption where it is not possible to differentiate which type of service is being produced.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9820":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9820."}
    return await task_open_isic_classify_entity(**kwargs)
