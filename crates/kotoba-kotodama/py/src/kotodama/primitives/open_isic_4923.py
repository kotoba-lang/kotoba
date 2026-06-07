from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4923_classify(**kwargs: Any) -> dict[str, Any]:
    """Freight transport by road.

    This class includes all road freight transport activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4923":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4923."}
    return await task_open_isic_classify_entity(**kwargs)
