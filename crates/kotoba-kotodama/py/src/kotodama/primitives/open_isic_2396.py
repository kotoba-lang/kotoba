from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2396_classify(**kwargs: Any) -> dict[str, Any]:
    """Cutting, shaping and finishing of stone

    This class includes the cutting, shaping and finishing of stone for construction and other purposes.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2396":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2396."}
    return await task_open_isic_classify_entity(**kwargs)
