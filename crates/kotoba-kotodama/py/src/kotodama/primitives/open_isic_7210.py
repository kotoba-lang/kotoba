from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7210_classify(**kwargs: Any) -> dict[str, Any]:
    """Research and experimental development on natural sciences and engineering

    This class includes the activities of industrial research laboratories engaged in systematic original investigation in natural sciences and engineering.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7210":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7210."}
    return await task_open_isic_classify_entity(**kwargs)
