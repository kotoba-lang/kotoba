from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0230_classify(**kwargs: Any) -> dict[str, Any]:
    """Gathering of non-wood forest products.

    This class includes the gathering of wild growing non-wood forest products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0230":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0230."}
    return await task_open_isic_classify_entity(**kwargs)
