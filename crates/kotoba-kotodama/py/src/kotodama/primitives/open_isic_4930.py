from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4930_classify(**kwargs: Any) -> dict[str, Any]:
    """Transport via pipeline.

    This class includes the transport of gases, liquids, slurry and other commodities via pipeline.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4930":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4930."}
    return await task_open_isic_classify_entity(**kwargs)
