from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6621_classify(**kwargs: Any) -> dict[str, Any]:
    """Risk and damage evaluation.

    This class includes assessment of risks and damages for insurance purposes.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6621":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6621."}
    return await task_open_isic_classify_entity(**kwargs)
