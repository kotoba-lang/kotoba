from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0116_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of fibre crops.

    This class includes the growing of fibre crops such as cotton, jute, flax and hemp.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0116":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0116."}
    return await task_open_isic_classify_entity(**kwargs)
