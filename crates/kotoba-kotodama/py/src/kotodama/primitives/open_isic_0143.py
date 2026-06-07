from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0143_classify(**kwargs: Any) -> dict[str, Any]:
    """Raising of camels and camelids.

    This class includes raising and breeding of camels (dromedary) and other camelids.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0143":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0143."}
    return await task_open_isic_classify_entity(**kwargs)
