from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7220_classify(**kwargs: Any) -> dict[str, Any]:
    """Research and experimental development on social sciences and humanities

    This class includes the activities of laboratories and institutes engaged in systematic original investigation in social sciences and humanities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7220":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7220."}
    return await task_open_isic_classify_entity(**kwargs)
