from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0240_classify(**kwargs: Any) -> dict[str, Any]:
    """Support services to forestry.

    This class includes the carrying out of part of the forestry operation on a fee or contract basis, including forestry service activities (inventories, consulting, evaluation, pest control, fire protection), logging service activities (transport within the forest).
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0240":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0240."}
    return await task_open_isic_classify_entity(**kwargs)
