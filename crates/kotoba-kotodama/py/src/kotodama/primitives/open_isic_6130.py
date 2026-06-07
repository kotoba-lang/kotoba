from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6130_classify(**kwargs: Any) -> dict[str, Any]:
    """Satellite telecommunications activities.

    This class includes operating, maintaining or providing access to satellite communications facilities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6130":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6130."}
    return await task_open_isic_classify_entity(**kwargs)
