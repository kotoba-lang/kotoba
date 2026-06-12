from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2829_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other special-purpose machinery.

    This class includes the manufacture of special-purpose machinery not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2829":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2829."}
    return await task_open_isic_classify_entity(**kwargs)
