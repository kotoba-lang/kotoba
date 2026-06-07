from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1104_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of soft drinks; production of mineral waters and other bottled waters

    This class includes the manufacture of non-alcoholic beverages, including bottled water, soft drinks, fruit juices and other non-alcoholic drinks.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1104":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1104."}
    return await task_open_isic_classify_entity(**kwargs)
