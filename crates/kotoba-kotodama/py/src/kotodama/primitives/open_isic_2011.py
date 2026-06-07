from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2011_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of basic chemicals

    This class includes the manufacture of basic chemicals such as industrial gases, inorganic and organic chemicals, and petrochemicals.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2011":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2011."}
    return await task_open_isic_classify_entity(**kwargs)
