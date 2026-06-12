from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5610_classify(**kwargs: Any) -> dict[str, Any]:
    """Restaurants and mobile food service activities

    This class includes the provision of food services to customers, whether they are served while seated or serve themselves from a display of items.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5610":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5610."}
    return await task_open_isic_classify_entity(**kwargs)
