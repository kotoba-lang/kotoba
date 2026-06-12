from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4330_classify(**kwargs: Any) -> dict[str, Any]:
    """Building completion and finishing.

    This class includes activities that contribute to the completion or finishing of a construction.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4330":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4330."}
    return await task_open_isic_classify_entity(**kwargs)
