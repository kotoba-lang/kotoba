from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7810_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of employment placement agencies

    This class includes listing employment vacancies and referring or placing applicants for employment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7810":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7810."}
    return await task_open_isic_classify_entity(**kwargs)
