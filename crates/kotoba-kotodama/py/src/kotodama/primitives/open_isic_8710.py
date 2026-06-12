from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8710_classify(**kwargs: Any) -> dict[str, Any]:
    """Residential nursing care facilities

    This class includes the provision of residential care combined with either nursing, supervisory, or other types of care as required by the inhabitants.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8710":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8710."}
    return await task_open_isic_classify_entity(**kwargs)
