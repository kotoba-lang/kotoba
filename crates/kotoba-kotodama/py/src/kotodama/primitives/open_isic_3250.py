from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3250_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of medical and dental instruments and supplies.

    This class includes the manufacture of medical, surgical, dental and veterinary instruments and supplies.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3250":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3250."}
    return await task_open_isic_classify_entity(**kwargs)
