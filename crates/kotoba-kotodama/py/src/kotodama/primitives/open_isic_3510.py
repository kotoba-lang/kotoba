from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3510_classify(**kwargs: Any) -> dict[str, Any]:
    """Electric power generation, transmission and distribution.

    This class includes the generation of bulk electric power, and its transmission and distribution to end users.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3510":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3510."}
    return await task_open_isic_classify_entity(**kwargs)
