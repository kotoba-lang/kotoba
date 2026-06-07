from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8130_classify(**kwargs: Any) -> dict[str, Any]:
    """Landscape care and maintenance service activities

    This class includes the planting, care and maintenance of parks, gardens, landscapes and lawns.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8130":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8130."}
    return await task_open_isic_classify_entity(**kwargs)
