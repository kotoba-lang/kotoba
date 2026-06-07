from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8030_classify(**kwargs: Any) -> dict[str, Any]:
    """Investigation activities

    This class includes the investigation activities carried out by private detective agencies, private investigators, and insurance investigators.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8030":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8030."}
    return await task_open_isic_classify_entity(**kwargs)
