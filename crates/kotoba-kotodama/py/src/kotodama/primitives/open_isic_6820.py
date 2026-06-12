from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6820_classify(**kwargs: Any) -> dict[str, Any]:
    """Real estate activities on a fee or contract basis.

    This class includes the provision of real estate activities on behalf of others.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6820":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6820."}
    return await task_open_isic_classify_entity(**kwargs)
