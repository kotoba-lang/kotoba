from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8291_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of collection agencies and credit bureaus

    This class includes activities of collecting overdue accounts, and activities of credit bureaus.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8291":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8291."}
    return await task_open_isic_classify_entity(**kwargs)
