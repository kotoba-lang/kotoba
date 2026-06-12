from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8423_classify(**kwargs: Any) -> dict[str, Any]:
    """Public order and safety activities

    This class includes activities of the provision of public order and safety services.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8423":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8423."}
    return await task_open_isic_classify_entity(**kwargs)
