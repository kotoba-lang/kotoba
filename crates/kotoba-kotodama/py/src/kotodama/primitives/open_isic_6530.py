from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6530_classify(**kwargs: Any) -> dict[str, Any]:
    """Pension funding.

    This class includes the establishment, management and administration of pension funds, except compulsory social security.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6530":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6530."}
    return await task_open_isic_classify_entity(**kwargs)
