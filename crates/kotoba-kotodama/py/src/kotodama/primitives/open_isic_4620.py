from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4620_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of agricultural raw materials and live animals

    This class includes the wholesale of agricultural raw materials, live animals and animal raw materials.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4620":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4620."}
    return await task_open_isic_classify_entity(**kwargs)
