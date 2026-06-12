from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2592_classify(**kwargs: Any) -> dict[str, Any]:
    """Treatment and coating of metals; machining.

    This class includes the treatment and coating of metals and the general machining of metal parts.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2592":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2592."}
    return await task_open_isic_classify_entity(**kwargs)
