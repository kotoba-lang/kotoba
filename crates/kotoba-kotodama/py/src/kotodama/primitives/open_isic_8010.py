from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8010_classify(**kwargs: Any) -> dict[str, Any]:
    """Private security activities

    This class includes the provision of one or more of the following: guard services, patrol services, watchman services, armored car services and guard dog services.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8010":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8010."}
    return await task_open_isic_classify_entity(**kwargs)
