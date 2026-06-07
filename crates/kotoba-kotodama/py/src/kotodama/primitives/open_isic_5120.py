from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5120_classify(**kwargs: Any) -> dict[str, Any]:
    """Freight air transport and space transport

    This class includes the transport of freight by air and all space transport.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5120":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5120."}
    return await task_open_isic_classify_entity(**kwargs)
