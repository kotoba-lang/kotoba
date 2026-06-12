from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7911_classify(**kwargs: Any) -> dict[str, Any]:
    """Travel agency activities

    This class includes the activities of agencies primarily engaged in selling travel, tour, transportation and accommodation services to the general public.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7911":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7911."}
    return await task_open_isic_classify_entity(**kwargs)
