from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7310_classify(**kwargs: Any) -> dict[str, Any]:
    """Advertising

    This class includes the creation of advertising campaigns and placement of such advertising in periodicals, newspapers, radio and television, the internet and other media.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7310":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7310."}
    return await task_open_isic_classify_entity(**kwargs)
