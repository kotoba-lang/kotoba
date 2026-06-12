from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6020_classify(**kwargs: Any) -> dict[str, Any]:
    """Television programming and broadcasting activities.

    This class includes the broadcasting of visual content to the public.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6020":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6020."}
    return await task_open_isic_classify_entity(**kwargs)
