from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1075_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of prepared meals and dishes

    This class includes the manufacture of ready-to-eat meals and dishes that are packaged and sold for home consumption.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1075":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1075."}
    return await task_open_isic_classify_entity(**kwargs)
