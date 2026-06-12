from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8522_classify(**kwargs: Any) -> dict[str, Any]:
    """Technical and vocational secondary education

    This class includes the provision of secondary education with technical and vocational emphasis.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8522":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8522."}
    return await task_open_isic_classify_entity(**kwargs)
