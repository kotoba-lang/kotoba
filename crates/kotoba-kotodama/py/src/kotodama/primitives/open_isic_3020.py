from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3020_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of railway locomotives and rolling stock.

    This class includes the manufacture of railway and tramway locomotives and rolling stock.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3020":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3020."}
    return await task_open_isic_classify_entity(**kwargs)
