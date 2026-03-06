#!/usr/bin/env python3.12
"""
TCP debug listener — measures events/sec and latency from event timestamps.
"""

import asyncio
import orjson
import time
from collections import defaultdict
from dataclasses import dataclass, field


# ── Config ────────────────────────────────────────────────────────────────────

PORTS = [9001, 9002]  # TCP ports to listen on
PRINT_INTERVAL = 3.0  # seconds between stats printout
TIMESTAMP_FIELD = "ts"  # JSON field with unix timestamp (sec or ms)
RECV_BUFFER = 1 << 16  # 64KB reads


# ── Per-port stats ────────────────────────────────────────────────────────────


@dataclass
class PortStats:
    events: int = 0
    latencies: list = field(default_factory=list)  # ms
    errors: int = 0
    # snapshot from last print interval
    last_events: int = 0
    last_time: float = field(default_factory=time.monotonic)


stats: dict[int, PortStats] = defaultdict(PortStats)


# ── Event parsing ─────────────────────────────────────────────────────────────


def parse_events(raw: bytes) -> list[dict]:
    """
    Handle the common case where a single recv() contains multiple newline-
    delimited JSON objects, or a partial final line (which we discard —
    the next recv will complete it).  Also handles bare objects with no newline.
    """
    events = []
    for line in raw.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return events


def measure(port: int, events: list[dict]) -> None:
    now = time.time()
    s = stats[port]
    s.events += len(events)
    for ev in events:
        raw_ts = ev.get(TIMESTAMP_FIELD)
        if raw_ts is None:
            continue
        # Accept seconds or milliseconds automatically
        if raw_ts > 1e12:  # milliseconds
            raw_ts /= 1000.0
        latency_ms = (now - raw_ts) * 1000.0
        if latency_ms >= 0:  # ignore obviously wrong clocks
            s.latencies.append(latency_ms)


# ── Async connection handler ──────────────────────────────────────────────────


async def handle_connection(reader: asyncio.StreamReader, port: int) -> None:
    s = stats[port]
    try:
        while True:
            data = await reader.read(RECV_BUFFER)
            if not data:
                break
            events = parse_events(data)
            measure(port, events)
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    except Exception as e:
        s.errors += 1


def make_handler(port: int):
    async def _handler(reader, writer):
        writer.transport.set_write_buffer_limits(0)  # don't buffer writes
        await handle_connection(reader, port)
        writer.close()

    return _handler


# ── Stats printer ─────────────────────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    data = sorted(data)
    idx = (len(data) - 1) * p / 100
    lo, hi = int(idx), min(int(idx) + 1, len(data) - 1)
    return data[lo] + (data[hi] - data[lo]) * (idx - lo)


async def print_loop(interval: float, ports: list[int]) -> None:
    await asyncio.sleep(interval)  # let first window fill
    while True:
        now = time.monotonic()
        print(f"\n{BOLD}{'─' * 56}{RESET}")
        print(f"{BOLD}  TCP Debug Listener  {DIM}{time.strftime('%H:%M:%S')}{RESET}")
        print(f"{BOLD}{'─' * 56}{RESET}")

        for port in ports:
            s = stats[port]
            elapsed = now - s.last_time
            new_events = s.events - s.last_events
            eps = new_events / elapsed if elapsed > 0 else 0.0

            lats = s.latencies
            avg = sum(lats) / len(lats) if lats else 0.0
            p50 = percentile(lats, 50)
            p99 = percentile(lats, 99)

            # Color eps by rough threshold
            eps_color = GREEN if eps > 100 else YELLOW if eps > 0 else DIM

            print(f"  {CYAN}:{port}{RESET}")
            print(
                f"    events/sec  {eps_color}{eps:>10,.1f}{RESET}   "
                f"(total {s.events:,})"
            )

            if lats:
                lat_color = GREEN if avg < 50 else YELLOW if avg < 500 else RED
                print(
                    f"    latency ms  {lat_color}avg {avg:>7.1f}  "
                    f"p50 {p50:>7.1f}  p99 {p99:>7.1f}{RESET}"
                )
            else:
                print(
                    f"    latency     {DIM}no timestamp field '{TIMESTAMP_FIELD}' found{RESET}"
                )

            if s.errors:
                print(f"    {RED}errors      {s.errors}{RESET}")

            # Reset for next window
            s.last_events = s.events
            s.last_time = now
            s.latencies = []

        print(f"{DIM}{'─' * 56}{RESET}", flush=True)
        await asyncio.sleep(interval)


# ── Main ──────────────────────────────────────────────────────────────────────


async def main():
    servers = []
    for port in PORTS:
        server = await asyncio.start_server(make_handler(port), "0.0.0.0", port)
        servers.append(server)
        print(f"  {GREEN}listening{RESET} on :{port}")

    print(
        f"  {DIM}printing every {PRINT_INTERVAL}s  |  "
        f"timestamp field: '{TIMESTAMP_FIELD}'{RESET}\n"
    )

    async with asyncio.TaskGroup() as tg:
        for server in servers:
            tg.create_task(server.serve_forever())
        tg.create_task(print_loop(PRINT_INTERVAL, PORTS))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbye")
