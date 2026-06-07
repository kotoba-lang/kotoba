from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3011_classify(**kwargs: Any) -> dict[str, Any]:
    """Building of ships and floating structures.

    This class includes the building of ships and floating structures for commercial and other uses.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3011":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3011."}
    return await task_open_isic_classify_entity(**kwargs)
