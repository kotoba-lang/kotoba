from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2731_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of fibre optic cables.

    This class includes the manufacture of fibre optic cables for data transmission or live transmission of images.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2731":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2731."}
    return await task_open_isic_classify_entity(**kwargs)
