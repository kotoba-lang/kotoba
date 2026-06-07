from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2310_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of glass and glass products

    This class includes the manufacture of glass in all its basic forms and glass products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2310":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2310."}
    return await task_open_isic_classify_entity(**kwargs)
