from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2512_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of tanks, reservoirs and containers of metal.

    This class includes the manufacture of tanks, reservoirs and containers of metal for storage or manufacturing use.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2512":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2512."}
    return await task_open_isic_classify_entity(**kwargs)
