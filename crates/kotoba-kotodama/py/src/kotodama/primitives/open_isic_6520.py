from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6520_classify(**kwargs: Any) -> dict[str, Any]:
    """Reinsurance.

    This class includes the activities of assuming all or part of the risk associated with existing insurance policies originally underwritten by other insurance carriers.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6520":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6520."}
    return await task_open_isic_classify_entity(**kwargs)
