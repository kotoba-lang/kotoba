from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3600_classify(**kwargs: Any) -> dict[str, Any]:
    """Water collection, treatment and supply.

    This class includes the purification and distribution of water for domestic and industrial purposes.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3600":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3600."}
    return await task_open_isic_classify_entity(**kwargs)
