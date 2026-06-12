from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5811_classify(**kwargs: Any) -> dict[str, Any]:
    """Book publishing

    This class includes the publishing of books in print and electronic form.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5811":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5811."}
    return await task_open_isic_classify_entity(**kwargs)
