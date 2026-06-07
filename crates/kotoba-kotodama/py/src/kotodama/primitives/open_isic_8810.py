from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8810_classify(**kwargs: Any) -> dict[str, Any]:
    """Social work activities without accommodation for the elderly and disabled

    This class includes the provision of social assistance services directly to the elderly and disabled without providing accommodation.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8810":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8810."}
    return await task_open_isic_classify_entity(**kwargs)
