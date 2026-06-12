from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8890_classify(**kwargs: Any) -> dict[str, Any]:
    """Other social work activities without accommodation

    This class includes other social work activities not elsewhere classified, where accommodation is not provided.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8890":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8890."}
    return await task_open_isic_classify_entity(**kwargs)
