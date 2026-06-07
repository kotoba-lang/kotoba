from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6511_classify(**kwargs: Any) -> dict[str, Any]:
    """Life insurance.

    This class includes the underwriting of life insurance annuities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6511":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6511."}
    return await task_open_isic_classify_entity(**kwargs)
