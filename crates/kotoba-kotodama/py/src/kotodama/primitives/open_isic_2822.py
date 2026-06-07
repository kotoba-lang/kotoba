from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2822_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of metal-forming machinery and machine tools.

    This class includes the manufacture of machine tools for working metal and other materials, and metal-forming machinery.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2822":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2822."}
    return await task_open_isic_classify_entity(**kwargs)
