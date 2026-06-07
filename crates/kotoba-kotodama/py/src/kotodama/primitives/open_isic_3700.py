from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3700_classify(**kwargs: Any) -> dict[str, Any]:
    """Sewerage.

    This class includes the operation of sewer systems or sewage treatment facilities that collect, treat, and dispose of sewage.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3700":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3700."}
    return await task_open_isic_classify_entity(**kwargs)
