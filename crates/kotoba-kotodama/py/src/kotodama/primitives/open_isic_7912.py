from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7912_classify(**kwargs: Any) -> dict[str, Any]:
    """Tour operator activities

    This class includes the activities of tour operators primarily engaged in assembling and arranging tours sold through travel agencies or directly to individual travellers.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7912":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7912."}
    return await task_open_isic_classify_entity(**kwargs)
