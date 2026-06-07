from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7830_classify(**kwargs: Any) -> dict[str, Any]:
    """Other human resources provision

    This class includes providing human resources for client businesses, where the client directs the work, but the service provider is responsible for the employment of the workers.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7830":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7830."}
    return await task_open_isic_classify_entity(**kwargs)
