from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4665_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of other intermediate products

    This class includes the wholesale of other intermediate products used in production.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4665":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4665."}
    return await task_open_isic_classify_entity(**kwargs)
