from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1101_classify(**kwargs: Any) -> dict[str, Any]:
    """Distilling, rectifying and blending of spirits

    This class includes the manufacture of distilled, rectified and blended spirits such as whisky, brandy, gin, vodka, rum and liqueurs.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1101":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1101."}
    return await task_open_isic_classify_entity(**kwargs)
