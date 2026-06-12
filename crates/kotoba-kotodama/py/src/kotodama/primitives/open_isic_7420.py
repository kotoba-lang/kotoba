from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7420_classify(**kwargs: Any) -> dict[str, Any]:
    """Photographic activities

    This class includes the production of still or moving photographic images.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7420":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7420."}
    return await task_open_isic_classify_entity(**kwargs)
