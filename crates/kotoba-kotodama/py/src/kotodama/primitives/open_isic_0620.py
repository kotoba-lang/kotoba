from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0620_classify(**kwargs: Any) -> dict[str, Any]:
    """Extraction of natural gas.

    This class includes the extraction and production of natural gas from natural deposits. It includes the operation of natural gas wells, associated activities, and treatment of natural gas for delivery to market.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0620":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0620."}
    return await task_open_isic_classify_entity(**kwargs)
