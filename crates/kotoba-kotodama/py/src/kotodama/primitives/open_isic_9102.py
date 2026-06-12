from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9102_classify(**kwargs: Any) -> dict[str, Any]:
    """Museums activities and operation of historical sites and buildings

    This class includes the activities of museums of all kinds and the preservation and operation of historical sites and buildings.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9102":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9102."}
    return await task_open_isic_classify_entity(**kwargs)
