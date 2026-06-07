from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4540_classify(**kwargs: Any) -> dict[str, Any]:
    """Sale, maintenance and repair of motorcycles and related parts and accessories

    This class includes the sale, maintenance and repair of motorcycles and their parts and accessories.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4540":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4540."}
    return await task_open_isic_classify_entity(**kwargs)
