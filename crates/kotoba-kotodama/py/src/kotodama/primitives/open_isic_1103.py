from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1103_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of malt liquors and malt

    This class includes the manufacture of beer, ale, porter, stout and other malt liquors, and the manufacture of malt.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1103":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1103."}
    return await task_open_isic_classify_entity(**kwargs)
