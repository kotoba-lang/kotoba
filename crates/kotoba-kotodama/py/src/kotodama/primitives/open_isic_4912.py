from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4912_classify(**kwargs: Any) -> dict[str, Any]:
    """Freight rail transport.

    This class includes all rail freight transport operations.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4912":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4912."}
    return await task_open_isic_classify_entity(**kwargs)
