from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2392_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of clay building materials

    This class includes the manufacture of clay building materials such as bricks, roofing tiles and other clay construction products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2392":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2392."}
    return await task_open_isic_classify_entity(**kwargs)
