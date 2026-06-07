from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4312_classify(**kwargs: Any) -> dict[str, Any]:
    """Site preparation.

    This class includes the preparation of sites for subsequent construction activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4312":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4312."}
    return await task_open_isic_classify_entity(**kwargs)
