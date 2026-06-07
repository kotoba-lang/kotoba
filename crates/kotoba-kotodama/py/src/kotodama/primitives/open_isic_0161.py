from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0161_classify(**kwargs: Any) -> dict[str, Any]:
    """Support activities for crop production.

    This class includes activities incidental to agricultural production and activities similar to agriculture not undertaken for production purposes (in the sense of harvesting agricultural products), done on a fee or contract basis. Also includes post-harvest crop activities aimed at preparing agricultural products for the primary market.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0161":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0161."}
    return await task_open_isic_classify_entity(**kwargs)
