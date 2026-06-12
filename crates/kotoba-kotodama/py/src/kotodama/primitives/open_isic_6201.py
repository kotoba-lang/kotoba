from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6201_classify(**kwargs: Any) -> dict[str, Any]:
    """Computer programming activities.

    This class includes the writing, modifying, testing and supporting of software.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6201":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6201."}
    return await task_open_isic_classify_entity(**kwargs)
