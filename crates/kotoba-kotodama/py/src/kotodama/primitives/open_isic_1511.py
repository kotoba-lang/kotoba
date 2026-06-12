from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1511_classify(**kwargs: Any) -> dict[str, Any]:
    """Tanning and dressing of leather; dressing and dyeing of fur

    This class includes the tanning, dyeing and dressing of hides and skins, and the dressing and dyeing of fur skins.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1511":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1511."}
    return await task_open_isic_classify_entity(**kwargs)
