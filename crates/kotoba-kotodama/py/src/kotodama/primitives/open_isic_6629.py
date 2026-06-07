from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6629_classify(**kwargs: Any) -> dict[str, Any]:
    """Other activities auxiliary to insurance and pension funding.

    This class includes other auxiliary activities for insurance and pension funding not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6629":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6629."}
    return await task_open_isic_classify_entity(**kwargs)
