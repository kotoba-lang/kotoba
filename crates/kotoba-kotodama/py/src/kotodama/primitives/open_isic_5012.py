from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5012_classify(**kwargs: Any) -> dict[str, Any]:
    """Sea and coastal freight water transport

    This class includes the transport of freight on sea-going vessels.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5012":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5012."}
    return await task_open_isic_classify_entity(**kwargs)
