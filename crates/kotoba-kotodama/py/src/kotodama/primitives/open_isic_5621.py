from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5621_classify(**kwargs: Any) -> dict[str, Any]:
    """Event catering

    This class includes the provision of food services based on contractual arrangements with the customer for specific events.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5621":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5621."}
    return await task_open_isic_classify_entity(**kwargs)
