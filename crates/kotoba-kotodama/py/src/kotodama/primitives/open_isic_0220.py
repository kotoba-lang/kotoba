from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0220_classify(**kwargs: Any) -> dict[str, Any]:
    """Logging.

    This class includes production of roundwood for forest-based manufacturing industries, extraction and gathering of wild growing non-wood forest products. Besides the production of timber, forestry activities result in products that undergo little processing, such as fire wood, charcoal, wood chips and roundwood used in an unprocessed form (e.g. pit-props, pulpwood, etc.).
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0220":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0220."}
    return await task_open_isic_classify_entity(**kwargs)
