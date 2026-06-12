from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0144_classify(**kwargs: Any) -> dict[str, Any]:
    """Raising of sheep and goats.

    This class includes raising and breeding of sheep and goats, including the production of raw milk and wool.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0144":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0144."}
    return await task_open_isic_classify_entity(**kwargs)
