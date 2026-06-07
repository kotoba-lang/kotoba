from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0990_classify(**kwargs: Any) -> dict[str, Any]:
    """Support activities for other mining and quarrying

    This class includes support activities for other mining and quarrying activities, on a fee or contract basis.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0990":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0990."}
    return await task_open_isic_classify_entity(**kwargs)
