from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8129_classify(**kwargs: Any) -> dict[str, Any]:
    """Other building and industrial cleaning activities

    This class includes specialized cleaning activities for buildings and industrial facilities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8129":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8129."}
    return await task_open_isic_classify_entity(**kwargs)
