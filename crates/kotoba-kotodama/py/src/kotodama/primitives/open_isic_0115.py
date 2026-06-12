from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0115_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of tobacco.

    This class includes the growing of unmanufactured tobacco and the preliminary preparation of tobacco leaves (drying, curing).
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0115":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0115."}
    return await task_open_isic_classify_entity(**kwargs)
