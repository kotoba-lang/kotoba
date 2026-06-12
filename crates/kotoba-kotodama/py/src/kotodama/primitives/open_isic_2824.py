from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2824_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of machinery for mining, quarrying and construction.

    This class includes the manufacture of machinery used in mining, quarrying, and construction activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2824":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2824."}
    return await task_open_isic_classify_entity(**kwargs)
