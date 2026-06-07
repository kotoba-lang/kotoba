from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8292_classify(**kwargs: Any) -> dict[str, Any]:
    """Packaging activities

    This class includes packaging activities on a fee or contract basis, whether or not these involve an automated process.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8292":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8292."}
    return await task_open_isic_classify_entity(**kwargs)
