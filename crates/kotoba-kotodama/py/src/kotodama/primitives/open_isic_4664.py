from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4664_classify(**kwargs: Any) -> dict[str, Any]:
    """Wholesale of professional and scientific equipment

    This class includes the wholesale of professional, scientific and precision instruments and equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4664":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4664."}
    return await task_open_isic_classify_entity(**kwargs)
