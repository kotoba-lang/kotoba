from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6312_classify(**kwargs: Any) -> dict[str, Any]:
    """Web portals.

    This class includes the operation of web sites that use a search engine to generate and maintain extensive databases of Internet addresses and content.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6312":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6312."}
    return await task_open_isic_classify_entity(**kwargs)
