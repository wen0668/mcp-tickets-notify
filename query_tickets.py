#!/usr/bin/env python3
import argparse
import json
import re
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SessionReader(threading.Thread):
    def __init__(self, url, result):
        super().__init__(daemon=True)
        self.url = url
        self.result = result

    def run(self):
        try:
            req = Request(self.url, headers={"Accept": "text/event-stream"})
            with urlopen(req, timeout=30) as resp:
                for raw_line in resp:
                    if self.result["stop"].is_set():
                        break
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data.startswith("/message?"):
                            self.result["endpoint"] = data
                            self.result["endpoint_found"].set()
                        else:
                            self._handle_message(data)
                    elif line.startswith("event:"):
                        self.result["last_event"] = line.split(":", 1)[1].strip()
                    if self.result["message_received"].is_set():
                        break
        except Exception as exc:
            self.result["error"] = str(exc)
            self.result["endpoint_found"].set()

    def _handle_message(self, data):
        try:
            payload = json.loads(data)
        except ValueError:
            payload = data
        self.result.setdefault("messages", []).append(payload)
        if isinstance(payload, dict) and payload.get("jsonrpc") == "2.0" and payload.get("id") == self.result["id"]:
            self.result["message_received"].set()


def parse_args():
    parser = argparse.ArgumentParser(description="Query MCP ticket service through /sse and /message session flow.")
    parser.add_argument("--host", default="http://192.168.0.4:31234", help="Base service URL, e.g. http://192.168.0.4:31234")
    parser.add_argument("--date", required=True, help="Travel date, e.g. 2026-06-21")
    parser.add_argument("--from-station", required=True, dest="from_station", help="Departure station name")
    parser.add_argument("--to-station", required=True, dest="to_station", help="Arrival station name")
    parser.add_argument("--after-time", dest="after_time", help="Only show trains departing after HH:MM, e.g. 19:30")
    parser.add_argument("--seat-type", dest="seat_type", help="Only show specified seat type, e.g. 二等座 or 一等座")
    parser.add_argument("--timeout", type=int, default=20, help="Timeout seconds for SSE and message response")
    return parser.parse_args()


def build_payload(date, from_station, to_station):
    return {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get-tickets",
            "arguments": {
                "date": date,
                "fromStation": from_station,
                "toStation": to_station,
            },
        },
        "id": 1,
    }


def filter_and_print_tickets(messages, args):
    """Extract ticket text from messages and filter by time and seat type."""
    
    # Extract text content from the response
    text = ""
    for msg in messages:
        if isinstance(msg, dict) and "result" in msg:
            content = msg["result"].get("content", [])
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    break
    
    if not text:
        return
    
    # Parse train entries
    lines = text.split("\n")
    entries = []
    current = None
    pattern = re.compile(r"^(?P<train>\S+)\s+(?P<route>.+?)\s+(?P<start>\d{2}:\d{2}) -> (?P<end>\d{2}:\d{2})")
    
    for line in lines:
        m = pattern.match(line)
        if m:
            current = {
                "train": m.group("train"),
                "route": m.group("route"),
                "start": m.group("start"),
                "end": m.group("end"),
                "details": []
            }
            entries.append(current)
        elif current is not None and line.strip().startswith("-"):
            current["details"].append(line.strip())
    
    # Filter entries
    print("\n" + "=" * 70)
    print("FILTERED RESULTS:")
    print("=" * 70)
    
    found = False
    for entry in entries:
        # Apply time filter
        if args.after_time and entry["start"] <= args.after_time:
            continue
        
        # Apply seat type filter
        if args.seat_type:
            seat_available = False
            for detail in entry["details"]:
                if f"- {args.seat_type}:" in detail and "无票" not in detail:
                    seat_available = True
                    break
            if not seat_available:
                continue
        
        found = True
        print(f"\n{entry['train']} {entry['route']} {entry['start']} -> {entry['end']}")
        for detail in entry["details"]:
            # Only print the requested seat type if specified, or all if not
            if args.seat_type:
                if f"- {args.seat_type}:" in detail:
                    print(f"  {detail}")
            else:
                print(f"  {detail}")
    
    if not found:
        print("\nNo tickets found matching the specified criteria.")
    print("=" * 70)


def run():
    args = parse_args()
    base_url = args.host.rstrip("/")
    sse_url = f"{base_url}/sse"

    result = {
        "endpoint": None,
        "endpoint_found": threading.Event(),
        "message_received": threading.Event(),
        "stop": threading.Event(),
        "id": 1,
        "last_event": None,
    }

    print(f"Opening SSE session: {sse_url}")
    reader = SessionReader(sse_url, result)
    reader.start()

    if not result["endpoint_found"].wait(args.timeout):
        result["stop"].set()
        print("ERROR: timeout waiting for SSE endpoint from /sse", file=sys.stderr)
        sys.exit(1)

    if result.get("error"):
        print(f"ERROR: SSE connection failed: {result['error']}", file=sys.stderr)
        sys.exit(1)

    endpoint = result.get("endpoint")
    if not endpoint:
        print("ERROR: no /message endpoint received from SSE", file=sys.stderr)
        sys.exit(1)

    message_url = f"{base_url}{endpoint}" if endpoint.startswith("/") else endpoint
    payload = build_payload(args.date, args.from_station, args.to_station)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    print(f"Sending ticket query to: {message_url}")
    req = Request(message_url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=args.timeout) as resp:
            resp_text = resp.read().decode("utf-8", errors="replace")
            print("POST response:")
            print(resp_text)
    except HTTPError as exc:
        print(f"HTTP error: {exc.code} {exc.reason}", file=sys.stderr)
        try:
            print(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            pass
        result["stop"].set()
        sys.exit(1)
    except URLError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        result["stop"].set()
        sys.exit(1)

    print("Waiting for SSE message response...")
    if result["message_received"].wait(args.timeout):
        messages = result.get("messages", [])
        if args.after_time or args.seat_type:
            # Run filtered output if filters specified
            filter_and_print_tickets(messages, args)
        else:
            # Show full output if no filters
            print("SSE message received:")
            for msg in messages:
                print(json.dumps(msg, ensure_ascii=False, indent=2))
    else:
        print("WARNING: no SSE response message received within timeout", file=sys.stderr)
        messages = result.get("messages", [])
        if messages:
            if args.after_time or args.seat_type:
                filter_and_print_tickets(messages, args)
            else:
                print("Partial SSE messages:")
                for msg in messages:
                    print(json.dumps(msg, ensure_ascii=False, indent=2))

    result["stop"].set()
    time.sleep(0.2)
    print("Done.")


if __name__ == "__main__":
    run()
