from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9412_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of professional membership organizations

    This class includes the activities of organizations whose members' interests centre on a specific professional discipline.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9412":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9412."}
    return await task_open_isic_classify_entity(**kwargs)
