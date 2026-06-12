from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5920_classify(**kwargs: Any) -> dict[str, Any]:
    """Sound recording and music publishing activities

    This class includes the production and release of original sound recordings and music publishing.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5920":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5920."}
    return await task_open_isic_classify_entity(**kwargs)
