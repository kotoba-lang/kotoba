from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4290_classify(**kwargs: Any) -> dict[str, Any]:
    """Construction of other civil engineering projects.

    This class includes the construction of civil engineering projects not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4290":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4290."}
    return await task_open_isic_classify_entity(**kwargs)
