from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5912_classify(**kwargs: Any) -> dict[str, Any]:
    """Motion picture, video and television programme post-production activities

    This class includes post-production activities such as editing, special effects and other post-production activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5912":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5912."}
    return await task_open_isic_classify_entity(**kwargs)
