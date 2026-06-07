from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9601_classify(**kwargs: Any) -> dict[str, Any]:
    """Washing and (dry-)cleaning of textile and fur products

    This class includes the washing, cleaning, dyeing, and pressing of textile products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9601":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9601."}
    return await task_open_isic_classify_entity(**kwargs)
