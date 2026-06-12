from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1702_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of corrugated paper and paperboard and of containers of paper and paperboard

    This class includes the manufacture of corrugated paper and paperboard and containers made from paper and paperboard.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1702":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1702."}
    return await task_open_isic_classify_entity(**kwargs)
