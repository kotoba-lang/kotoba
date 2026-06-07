from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4711_classify(**kwargs: Any) -> dict[str, Any]:
    """Retail sale in non-specialised stores with food, beverages or tobacco predominating.

    This class includes the retail sale of a large variety of goods of which food products, beverages or tobacco predominate.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4711":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4711."}
    return await task_open_isic_classify_entity(**kwargs)
