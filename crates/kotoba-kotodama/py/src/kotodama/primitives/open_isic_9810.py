from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9810_classify(**kwargs: Any) -> dict[str, Any]:
    """Undifferentiated goods-producing activities of private households for own use

    This class includes the activities of households that produce goods for their own final consumption where it is not possible to differentiate which type of good is being produced.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9810":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9810."}
    return await task_open_isic_classify_entity(**kwargs)
