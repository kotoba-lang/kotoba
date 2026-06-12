from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1393_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of carpets and rugs

    This class includes the manufacture of carpets, rugs and textile floor coverings.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1393":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1393."}
    return await task_open_isic_classify_entity(**kwargs)
