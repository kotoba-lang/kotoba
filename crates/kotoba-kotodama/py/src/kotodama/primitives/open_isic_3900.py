from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3900_classify(**kwargs: Any) -> dict[str, Any]:
    """Remediation activities and other waste management services.

    This class includes the provision of remediation services to contaminated sites, as well as other waste management services not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3900":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3900."}
    return await task_open_isic_classify_entity(**kwargs)
