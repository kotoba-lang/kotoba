from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2750_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of domestic appliances.

    This class includes the manufacture of household-type electric and non-electric appliances.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2750":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2750."}
    return await task_open_isic_classify_entity(**kwargs)
