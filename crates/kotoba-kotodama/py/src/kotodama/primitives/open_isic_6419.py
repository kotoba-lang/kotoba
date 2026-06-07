from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6419_classify(**kwargs: Any) -> dict[str, Any]:
    """Other monetary intermediation.

    This class includes the receiving of deposits and/or close substitutes for deposits and extending of credit or lending funds.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6419":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6419."}
    return await task_open_isic_classify_entity(**kwargs)
