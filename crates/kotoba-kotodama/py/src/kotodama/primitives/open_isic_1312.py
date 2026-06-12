from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_1312_classify(**kwargs: Any) -> dict[str, Any]:
    """Weaving of textiles

    This class includes the weaving of textiles from any textile material including cotton, wool, silk, flax and man-made fibres.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "1312":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 1312."}
    return await task_open_isic_classify_entity(**kwargs)
