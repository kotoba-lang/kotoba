from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0891_classify(**kwargs: Any) -> dict[str, Any]:
    """Mining of chemical and fertilizer minerals

    This class includes mining of natural phosphates and natural potassium salts, mining of native sulphur, mining of natural barium sulphate and carbonate, and other chemical and fertilizer minerals.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0891":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0891."}
    return await task_open_isic_classify_entity(**kwargs)
