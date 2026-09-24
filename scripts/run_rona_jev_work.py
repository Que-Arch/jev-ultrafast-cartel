import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from jev_ultrafast import Agent

WORK_ID = "CARTEL-JEV-RONA-20260924-001"
URL = "https://github.com/Anil-matcha/Open-Generative-AI"
GOAL = (
    "Knowledge intake task. Read the visible public repository page only. "
    "Do not click, type, submit, publish, authenticate, or change anything. "
    "Finish when the repository page has been observed so the Knowledge employee can record provenance."
)
started = datetime.now(timezone.utc).isoformat()
agent = Agent(URL, GOAL)
try:
    result = list(agent.run())[-1]
    page = result["page"]
    text = page.get("text", "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    evidence_lines = [
        line for line in lines
        if re.search(r"MIT|license|image|video|cinema|lip-sync|MuAPI|Generative AI", line, re.I)
    ][:30]
    receipt = {
        "schema": "cartel/knowledge-jev-readonly-receipt/v1",
        "work_id": WORK_ID,
        "owner": "rona",
        "employee_lane": "knowledge",
        "tool_chain": ["jev", "provenance_receipt"],
        "objective": "Observe a public repository page and preserve source evidence for Knowledge review.",
        "source": {
            "url": page["url"],
            "title": page["title"],
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "extracted_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "evidence_lines": evidence_lines,
        },
        "jev": {
            "status": result["status"],
            "decision_count": len(result["decisions"]),
            "history_steps": len(result["history"]),
            "model": result["decisions"][0].get("model"),
        },
        "classification": {
            "evidence_state": "EXTRACTED_PAGE_OBSERVATION",
            "knowledge_state": "REVIEW_REQUIRED",
            "publication": "HELD",
            "confidence": "not treated as truth score",
        },
        "safety": {
            "external_mutation": False,
            "authentication_used": False,
            "credentials_written": False,
            "customer_data_used": False,
            "payment_or_trading_action": False,
        },
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    out = Path(r"C:/Users/BIGSAM TECH/hermes-agent/.big5/results/CARTEL-JEV-RONA-20260924-001-receipt.json")
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "work_id": WORK_ID,
        "url": page["url"],
        "title": page["title"],
        "receipt": str(out),
        "external_mutation": False,
    }))
finally:
    agent.close()
