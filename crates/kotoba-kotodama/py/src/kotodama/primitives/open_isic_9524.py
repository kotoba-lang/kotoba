from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9524_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of furniture and home furnishings

    This class includes the repair and restoration of furniture and home furnishings.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9524":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9524."}
    return await task_open_isic_classify_entity(**kwargs)
