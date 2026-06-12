from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0610_classify(**kwargs: Any) -> dict[str, Any]:
    """Extraction of crude petroleum.

    This class includes the extraction and production of crude petroleum and bituminous oil from natural deposits. It includes the operation of oil wells and related activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0610":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0610."}
    return await task_open_isic_classify_entity(**kwargs)
