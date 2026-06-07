from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1313_classify(**kwargs: Any) -> dict[str, Any]:
    """Finishing of textiles

    This class includes bleaching, dyeing, dressing, finishing and similar work on yarns, woven fabrics and other textile articles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1313":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1313."}
    return await task_open_isic_classify_entity(**kwargs)
