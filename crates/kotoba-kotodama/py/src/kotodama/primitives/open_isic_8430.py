from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8430_classify(**kwargs: Any) -> dict[str, Any]:
    """Compulsory social security activities

    This class includes the funding and administration of government-provided social security programs.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8430":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8430."}
    return await task_open_isic_classify_entity(**kwargs)
