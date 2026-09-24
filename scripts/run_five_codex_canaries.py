import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from jev_ultrafast import Agent

CASES = [
    ("jev-repo-verification", "https://github.com/browser-use/jev-ultrafast"),
    ("sa-government-source", "https://www.gov.za/"),
    ("python-technical-source", "https://www.python.org/"),
    ("w3c-standards-source", "https://www.w3.org/"),
    ("open-generative-ai-repo", "https://github.com/Anil-matcha/Open-Generative-AI"),
]
GOAL = (
    "Read the visible page only. Do not click links, type text, submit forms, or change anything. "
    "Finish when the page is observed."
)
results = []
for name, url in CASES:
    started = datetime.now(timezone.utc).isoformat()
    agent = None
    try:
        agent = Agent(url, GOAL)
        result = list(agent.run())[-1]
        text = result["page"].get("text", "")
        results.append({
            "case": name,
            "url": result["page"]["url"],
            "title": result["page"]["title"],
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": result["status"],
            "history_steps": len(result["history"]),
            "decision_count": len(result["decisions"]),
            "model": result["decisions"][0].get("model"),
            "observed_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "external_mutation": False,
        })
        print(name, result["status"], flush=True)
    except Exception as exc:
        results.append({
            "case": name,
            "url": url,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "external_mutation": False,
        })
        print(name, "FAILED", type(exc).__name__, str(exc), flush=True)
    finally:
        if agent:
            agent.close()

receipt = {
    "schema": "cartel/jev-codex-subscription-canary/v3",
    "provider": "codex-cli subscription",
    "repository": "https://github.com/Que-Arch/jev-ultrafast-cartel",
    "adapter_commit": "7581be4a4aa78f13aabf30ce282f30da7d81621d",
    "cases": results,
    "passed": sum(r.get("status") == "done" for r in results),
    "total": len(results),
    "credentials_written": False,
    "publication": "NONE",
    "external_mutations": False,
}
out = Path(r"C:/Users/BIGSAM TECH/hermes-agent/.big5/results/jev-codex-subscription-canary-20260924.json")
out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print("RECEIPT", out, "PASSED", receipt["passed"], "OF", receipt["total"], flush=True)
