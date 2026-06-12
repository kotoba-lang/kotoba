from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6920_classify(**kwargs: Any) -> dict[str, Any]:
    """Accounting, bookkeeping and auditing activities; tax consultancy.

    This class includes recording of commercial transactions from businesses or others; preparation of financial statements; examination of accounting records and financial statements; preparation of personal and business income tax returns; advisory activities and representation of clients before tax authorities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6920":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6920."}
    return await task_open_isic_classify_entity(**kwargs)
