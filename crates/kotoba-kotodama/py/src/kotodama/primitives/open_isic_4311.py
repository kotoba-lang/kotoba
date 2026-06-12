from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4311_classify(**kwargs: Any) -> dict[str, Any]:
    """Demolition.

    This class includes the demolition or wrecking of buildings and other structures.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4311":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4311."}
    return await task_open_isic_classify_entity(**kwargs)
