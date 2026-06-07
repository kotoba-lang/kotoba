from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8790_classify(**kwargs: Any) -> dict[str, Any]:
    """Other residential care activities

    This class includes the provision of residential care activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8790":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8790."}
    return await task_open_isic_classify_entity(**kwargs)
