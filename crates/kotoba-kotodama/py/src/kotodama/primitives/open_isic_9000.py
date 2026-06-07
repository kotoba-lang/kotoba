from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9000_classify(**kwargs: Any) -> dict[str, Any]:
    """Creative, arts and entertainment activities

    This class includes the operation of arts facilities and the production of live theatrical presentations, concerts and opera or dance productions and other stage productions.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9000":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9000."}
    return await task_open_isic_classify_entity(**kwargs)
