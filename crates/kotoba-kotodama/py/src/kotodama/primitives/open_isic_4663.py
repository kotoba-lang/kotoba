from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4663_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of construction materials, hardware, plumbing and heating equipment and supplies

    This class includes the wholesale of construction materials and equipment for construction and repair.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4663":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4663."}
    return await task_open_isic_classify_entity(**kwargs)
