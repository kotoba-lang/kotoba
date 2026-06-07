from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5021_classify(**kwargs: Any) -> dict[str, Any]:
    """Inland passenger water transport

    This class includes the transport of passengers on inland waterways.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5021":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5021."}
    return await task_open_isic_classify_entity(**kwargs)
