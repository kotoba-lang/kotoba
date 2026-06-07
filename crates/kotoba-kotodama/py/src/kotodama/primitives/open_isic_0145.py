from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0145_classify(**kwargs: Any) -> dict[str, Any]:
    """Raising of swine/pigs.

    This class includes raising and breeding of swine and pigs.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0145":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0145."}
    return await task_open_isic_classify_entity(**kwargs)
