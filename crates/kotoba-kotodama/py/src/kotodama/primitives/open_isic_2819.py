from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2819_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of other general-purpose machinery.

    This class includes the manufacture of general-purpose machinery not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2819":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2819."}
    return await task_open_isic_classify_entity(**kwargs)
