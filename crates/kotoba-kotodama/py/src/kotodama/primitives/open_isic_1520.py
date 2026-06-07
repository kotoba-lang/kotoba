from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1520_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of footwear

    This class includes the manufacture of footwear of any material by any process, including moulding.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1520":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1520."}
    return await task_open_isic_classify_entity(**kwargs)
