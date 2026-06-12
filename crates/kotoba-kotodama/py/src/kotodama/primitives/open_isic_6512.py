from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6512_classify(**kwargs: Any) -> dict[str, Any]:
    """Non-life insurance.

    This class includes the underwriting of accident, fire, motor, marine, aviation, transport and other non-life insurance.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6512":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6512."}
    return await task_open_isic_classify_entity(**kwargs)
