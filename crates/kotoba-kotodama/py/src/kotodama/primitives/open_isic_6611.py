from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6611_classify(**kwargs: Any) -> dict[str, Any]:
    """Administration of financial markets.

    This class includes the operation and supervision of financial markets.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6611":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6611."}
    return await task_open_isic_classify_entity(**kwargs)
