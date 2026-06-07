from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9900_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of extraterritorial organizations and bodies

    This class includes the activities of international organizations such as the United Nations and its specialized agencies, regional bodies, the International Monetary Fund, the World Bank, the World Customs Organization, etc.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9900":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9900."}
    return await task_open_isic_classify_entity(**kwargs)
