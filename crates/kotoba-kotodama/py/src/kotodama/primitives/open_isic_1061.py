from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1061_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of grain mill products

    This class includes the milling of flour or meal from cereals and vegetables. It includes the milling, cleaning and polishing of rice, and manufacture of flour mixes and prepared blended flour and dough for bread, cakes, biscuits or pancakes.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1061":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1061."}
    return await task_open_isic_classify_entity(**kwargs)
