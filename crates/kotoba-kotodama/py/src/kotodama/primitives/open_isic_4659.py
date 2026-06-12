from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4659_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of other machinery and equipment

    This class includes the wholesale of other machinery and equipment not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4659":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4659."}
    return await task_open_isic_classify_entity(**kwargs)
