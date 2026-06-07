from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1391_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of knitted and crocheted fabrics

    This class includes the manufacture of knitted and crocheted fabrics and articles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1391":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1391."}
    return await task_open_isic_classify_entity(**kwargs)
