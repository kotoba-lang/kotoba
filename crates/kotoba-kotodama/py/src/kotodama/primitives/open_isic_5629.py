from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5629_classify(**kwargs: Any) -> dict[str, Any]:
    """Other food service activities

    This class includes food service activities for captive markets on a contractual basis.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5629":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5629."}
    return await task_open_isic_classify_entity(**kwargs)
