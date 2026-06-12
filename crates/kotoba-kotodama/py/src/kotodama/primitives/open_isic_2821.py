from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2821_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of agricultural and forestry machinery.

    This class includes the manufacture of machinery used in agriculture, horticulture, forestry, and related activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2821":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2821."}
    return await task_open_isic_classify_entity(**kwargs)
