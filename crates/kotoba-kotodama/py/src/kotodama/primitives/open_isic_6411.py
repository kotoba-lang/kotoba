from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6411_classify(**kwargs: Any) -> dict[str, Any]:
    """Central banking.

    This class includes the activities of central banks.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6411":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6411."}
    return await task_open_isic_classify_entity(**kwargs)
