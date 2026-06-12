from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1430_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of knitted and crocheted apparel

    This class includes the manufacture of knitted and crocheted wearing apparel.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1430":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1430."}
    return await task_open_isic_classify_entity(**kwargs)
