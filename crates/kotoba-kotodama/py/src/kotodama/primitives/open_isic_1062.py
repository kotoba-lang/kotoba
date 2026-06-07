from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1062_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of starches and starch products

    This class includes the wet milling of corn and other cereals to produce starch and starch derivatives, glucose and glucose syrups, gluten and gluten feed.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1062":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1062."}
    return await task_open_isic_classify_entity(**kwargs)
