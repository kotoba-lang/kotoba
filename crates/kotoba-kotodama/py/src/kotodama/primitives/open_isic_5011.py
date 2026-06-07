from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5011_classify(**kwargs: Any) -> dict[str, Any]:
    """Sea and coastal passenger water transport

    This class includes the transport of passengers on sea-going vessels along coastal and inland routes.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5011":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5011."}
    return await task_open_isic_classify_entity(**kwargs)
