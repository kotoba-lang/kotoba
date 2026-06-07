from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4322_classify(**kwargs: Any) -> dict[str, Any]:
    """Plumbing, heat and air-conditioning installation.

    This class includes the installation of plumbing, heating and air-conditioning systems in buildings.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4322":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4322."}
    return await task_open_isic_classify_entity(**kwargs)
