from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6120_classify(**kwargs: Any) -> dict[str, Any]:
    """Wireless telecommunications activities.

    This class includes operating and maintaining wireless telecommunications networks.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6120":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6120."}
    return await task_open_isic_classify_entity(**kwargs)
