from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4782_classify(**kwargs: Any) -> dict[str, Any]:
    """Retail sale via stalls and markets of textiles, clothing and footwear.

    This class includes the retail sale of textiles, clothing and footwear via market stalls.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4782":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4782."}
    return await task_open_isic_classify_entity(**kwargs)
