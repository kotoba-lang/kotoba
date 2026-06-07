from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8720_classify(**kwargs: Any) -> dict[str, Any]:
    """Residential care activities for mental retardation, mental health and substance abuse

    This class includes the provision of residential care for persons with intellectual disabilities, mental health issues or substance abuse problems.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8720":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8720."}
    return await task_open_isic_classify_entity(**kwargs)
