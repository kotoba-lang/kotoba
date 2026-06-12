from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2815_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of ovens, furnaces and furnace burners.

    This class includes the manufacture of industrial or laboratory furnaces and ovens, and furnace burners.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2815":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2815."}
    return await task_open_isic_classify_entity(**kwargs)
