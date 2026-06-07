from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9491_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of religious organizations

    This class includes the activities of religious organizations or individuals providing sermons, guidance, and other religious services.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9491":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9491."}
    return await task_open_isic_classify_entity(**kwargs)
