from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2431_classify(**kwargs: Any) -> dict[str, Any]:
    """Casting of iron and steel.

    This class includes the casting of iron and steel products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2431":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2431."}
    return await task_open_isic_classify_entity(**kwargs)
