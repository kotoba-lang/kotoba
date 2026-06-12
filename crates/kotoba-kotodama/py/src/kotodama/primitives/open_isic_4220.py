from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4220_classify(**kwargs: Any) -> dict[str, Any]:
    """Construction of utility projects.

    This class includes the construction of distribution lines for utilities and related buildings and structures.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4220":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4220."}
    return await task_open_isic_classify_entity(**kwargs)
