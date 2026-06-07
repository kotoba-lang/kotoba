from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4641_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of textiles, clothing and footwear

    This class includes the wholesale of textiles, clothing and footwear.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4641":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4641."}
    return await task_open_isic_classify_entity(**kwargs)
