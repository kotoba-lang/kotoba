from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2511_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of structural metal products.

    This class includes the manufacture of structural metal products for use in construction and civil engineering.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2511":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2511."}
    return await task_open_isic_classify_entity(**kwargs)
