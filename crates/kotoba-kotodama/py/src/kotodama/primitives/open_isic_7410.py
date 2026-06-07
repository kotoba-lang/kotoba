from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7410_classify(**kwargs: Any) -> dict[str, Any]:
    """Specialized design activities

    This class includes specialized design activities such as fashion, graphic and interior design.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7410":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7410."}
    return await task_open_isic_classify_entity(**kwargs)
