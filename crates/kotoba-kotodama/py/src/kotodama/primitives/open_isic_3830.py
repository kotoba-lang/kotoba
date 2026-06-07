from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3830_classify(**kwargs: Any) -> dict[str, Any]:
    """Dismantling of wrecks; materials recovery.

    This class includes the dismantling of wrecks of all kinds (cars, ships, computers, etc.) for materials recovery.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3830":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3830."}
    return await task_open_isic_classify_entity(**kwargs)
