from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1311_classify(**kwargs: Any) -> dict[str, Any]:
    """Preparation and spinning of textile fibres

    This class includes the preparation and spinning of textile fibres of all kinds, including natural fibres such as cotton, wool, silk and flax, as well as man-made fibres.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1311":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1311."}
    return await task_open_isic_classify_entity(**kwargs)
