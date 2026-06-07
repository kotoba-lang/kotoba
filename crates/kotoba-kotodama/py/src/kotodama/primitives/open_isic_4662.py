from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4662_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of metals and metal ores

    This class includes the wholesale of metal ores and metals, including precious metals.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4662":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4662."}
    return await task_open_isic_classify_entity(**kwargs)
