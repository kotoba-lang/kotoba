from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7110_classify(**kwargs: Any) -> dict[str, Any]:
    """Architectural and engineering activities and related technical consultancy

    This class includes the provision of architectural services, engineering services, drafting services, building inspection services and surveying and mapping services.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7110":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7110."}
    return await task_open_isic_classify_entity(**kwargs)
