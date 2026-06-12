from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5224_classify(**kwargs: Any) -> dict[str, Any]:
    """Cargo handling

    This class includes the loading and unloading of goods, luggage and freight regardless of mode of transport.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5224":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5224."}
    return await task_open_isic_classify_entity(**kwargs)
