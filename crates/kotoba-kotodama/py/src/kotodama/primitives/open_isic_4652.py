from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4652_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of electronic and telecommunications equipment and parts

    This class includes the wholesale of electronic and telecommunications equipment and parts.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4652":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4652."}
    return await task_open_isic_classify_entity(**kwargs)
