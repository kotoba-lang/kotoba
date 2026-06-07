from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0125_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of other tree and bush fruits and nuts

    This class includes the growing of berries, nuts and other tree and bush fruits.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0125":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0125."}
    return await task_open_isic_classify_entity(**kwargs)
