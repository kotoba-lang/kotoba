from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9411_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of business and employers membership organizations

    This class includes the activities of organizations whose members' interests centre on the development and prosperity of business enterprises.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9411":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9411."}
    return await task_open_isic_classify_entity(**kwargs)
