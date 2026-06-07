from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5813_classify(**kwargs: Any) -> dict[str, Any]:
    """Publishing of newspapers, journals and periodicals

    This class includes the publishing of newspapers, journals and other periodicals.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5813":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5813."}
    return await task_open_isic_classify_entity(**kwargs)
