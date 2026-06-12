from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9312_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of sports clubs

    This class includes the activities of sports clubs, which, whether or not operated for profit, are primarily engaged in promoting competitive or recreational sports activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9312":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9312."}
    return await task_open_isic_classify_entity(**kwargs)
