from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0129_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of other perennial crops

    This class includes the growing of other perennial crops, such as natural rubber trees and Christmas trees grown on plantations.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0129":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0129."}
    return await task_open_isic_classify_entity(**kwargs)
