from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2823_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of machinery for metallurgy.

    This class includes the manufacture of machines and equipment used in metallurgical processes.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2823":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2823."}
    return await task_open_isic_classify_entity(**kwargs)
