from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1709_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other articles of paper and paperboard

    This class includes the manufacture of other articles of paper and paperboard not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1709":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1709."}
    return await task_open_isic_classify_entity(**kwargs)
