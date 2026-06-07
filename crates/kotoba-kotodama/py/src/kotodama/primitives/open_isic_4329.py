from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4329_classify(**kwargs: Any) -> dict[str, Any]:
    """Other construction installation.

    This class includes installation activities not elsewhere classified in buildings and other structures.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4329":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4329."}
    return await task_open_isic_classify_entity(**kwargs)
