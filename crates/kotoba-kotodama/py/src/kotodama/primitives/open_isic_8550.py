from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8550_classify(**kwargs: Any) -> dict[str, Any]:
    """Educational support activities

    This class includes the provision of non-instructional activities that support educational processes or systems.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8550":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8550."}
    return await task_open_isic_classify_entity(**kwargs)
