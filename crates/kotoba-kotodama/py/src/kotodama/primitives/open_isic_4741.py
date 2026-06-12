from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4741_classify(**kwargs: Any) -> dict[str, Any]:
    """Retail sale of computers, peripheral units, software and telecommunications equipment in specialised stores.

    This class includes the retail sale of computers, peripherals, software and telecommunications equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4741":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4741."}
    return await task_open_isic_classify_entity(**kwargs)
