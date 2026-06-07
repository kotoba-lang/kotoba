from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1395_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of non-wovens and articles made from non-wovens, except apparel

    This class includes the manufacture of non-woven fabrics and articles made from non-wovens, except apparel.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1395":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1395."}
    return await task_open_isic_classify_entity(**kwargs)
