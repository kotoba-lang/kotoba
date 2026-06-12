from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2652_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of watches and clocks.

    This class includes the manufacture of watches, clocks and timing devices.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2652":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2652."}
    return await task_open_isic_classify_entity(**kwargs)
