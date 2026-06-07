from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5210_classify(**kwargs: Any) -> dict[str, Any]:
    """Warehousing and storage

    This class includes the operation of storage and warehouse facilities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5210":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5210."}
    return await task_open_isic_classify_entity(**kwargs)
