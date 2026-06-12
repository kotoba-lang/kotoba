from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8521_classify(**kwargs: Any) -> dict[str, Any]:
    """General secondary education

    This class includes the provision of general secondary education.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8521":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8521."}
    return await task_open_isic_classify_entity(**kwargs)
