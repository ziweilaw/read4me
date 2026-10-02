"""Line-delimited JSON-RPC over stdio. The Electron main process spawns this and talks to it.

Requests:  {"id": 1, "method": "load", "params": {"path": "..."}}
           {"id": 2, "method": "command", "params": {"text": "read chapter 2", "current_page": 0}}
           {"id": 3, "method": "units", "params": {"start": 4, "end": 5, "settings": {...}}}
Responses: {"id": 1, "result": ...} | {"id": 1, "error": "..."}
"""
import dataclasses
import json
import sys

from r4m.commands import parse_command
from r4m.pipeline import load
from r4m.reader import Settings, build_units
from r4m import tts

doc = None


def handle(method: str, p: dict):
    global doc
    if method == "ping":
        return "pong"
    if method == "load":
        doc = load(p["path"])
        return {
            "n_pages": doc.n_pages,
            "page_offset": doc.page_offset,
            "kind": doc.kind,
            "seg_titles": doc.seg_titles,
            "scanned_pages": doc.scanned_pages,
            "sections": [dataclasses.asdict(s) for s in doc.sections],
        }
    if method == "voices":
        return tts.voices(*([p["provider"]] if "provider" in p else []))
    if method == "speak":
        return tts.speak_b64(p["text"], p.get("voice", ""), **({"provider": p["provider"]} if "provider" in p else {}))
    if doc is None:
        raise RuntimeError("no document loaded")
    if method == "command":
        c = parse_command(p["text"], doc, p.get("current_page", 0))
        d = dataclasses.asdict(c)
        return d
    if method == "units":
        units = build_units(doc, p["start"], p["end"], Settings(**p.get("settings", {})))
        return [dataclasses.asdict(u) for u in units]
    raise ValueError(f"unknown method {method}")


def main():
    for line in sys.stdin:
        req = json.loads(line)
        try:
            out = {"id": req["id"], "result": handle(req["method"], req.get("params", {}))}
        except Exception as e:  # noqa: BLE001 - report to caller, keep serving
            out = {"id": req["id"], "error": str(e)}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
