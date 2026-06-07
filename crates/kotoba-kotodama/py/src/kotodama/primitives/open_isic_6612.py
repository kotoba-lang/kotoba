from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6612_classify(**kwargs: Any) -> dict[str, Any]:
    """Security and commodity contracts dealing activities.

    This class includes dealing in financial markets on behalf of others (e.g. stock broking) and related activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6612":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6612."}
    return await task_open_isic_classify_entity(**kwargs)
