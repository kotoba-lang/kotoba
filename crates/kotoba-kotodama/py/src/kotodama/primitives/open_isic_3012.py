from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3012_classify(**kwargs: Any) -> dict[str, Any]:
    """Building of pleasure and sporting boats.

    This class includes the building of pleasure and sporting boats.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3012":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3012."}
    return await task_open_isic_classify_entity(**kwargs)
