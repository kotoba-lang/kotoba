from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9521_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of consumer electronics

    This class includes the repair and maintenance of consumer electronics.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9521":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9521."}
    return await task_open_isic_classify_entity(**kwargs)
