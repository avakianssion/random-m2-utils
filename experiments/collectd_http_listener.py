#!/usr/bin/env python3
"""
Collectd HTTP Receiver

A lightweight HTTP server that receives JSON metrics data from collectd's write_http plugin

Usage:
    python3 collectd_http.py
    Note: Will likely add more flags here for batch size, send port, receive port, and more....

The server listens on http://0.0.0.0:6780/ and expects POST requests with JSON data
in collectd's format. Each metric is flattened and goes out as a separate JSON line

Collectd Configuration this code was tested with:

    <Plugin write_http>
      <Node "local">
        URL "http://your-server:6780/"
        Format "JSON"
        StoreRates false
      </Node>
    </Plugin>

"""
import asyncio
from aiohttp import web
import orjson
from threading import Thread
from queue import Queue
import signal
import sys


OUTFILE = "/data/collectd.out"
# This would have to change, likely a bigger batch size before we attempt to send, better yet, put this in a flag
BATCH_SIZE = 10 
batch_queue = Queue()
shutdown_event = asyncio.Event()

def udp_sender():
    """
    Out to udp worker. Would likely have to put this in a thread pool for better scaling
    """
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    buffer = []
    while True:
        item = batch_queue.get()
        if item is None:
            break
        buffer.append(item)
        
        if len(buffer) >= BATCH_SIZE:
            # Send batch as JSON array
            data = orjson.dumps(buffer)
            sock.sendto(data, ('localhost', 9999))
            buffer.clear()
    
    # Send remaining
    if buffer:
        data = orjson.dumps(buffer)
        sock.sendto(data, ('localhost', 9999))

def disk_writer():
    """
    disk write worker used for testing
    """
    buffer = []
    while True:
        item = batch_queue.get()
        if item is None:  # sentinel for shutdown
            break
        buffer.append(item)
        if len(buffer) >= BATCH_SIZE:
            with open(OUTFILE, "ab") as f:
                for m in buffer:
                    f.write(orjson.dumps(m) + b"\n")
            buffer.clear()
    
    # Flush remaining
    if buffer:
        with open(OUTFILE, "ab") as f:
            for m in buffer:
                f.write(orjson.dumps(m) + b"\n")

writer_thread = Thread(target=disk_writer, daemon=True)
writer_thread.start()

async def handle(request):
    """
    HTTP Handler
    """
    try:
        raw_body = await request.read()
        data = orjson.loads(raw_body)
    except orjson.JSONDecodeError:
        return web.Response(status=400, text="Invalid JSON\n")
    
    # Ensure data is a list, which collectd sends out as, it seems???
    if not isinstance(data, list):
        data = [data]
    
    measurements = []
    for item in data:
        time = item.get('time')
        host = item.get('host')
        plugin = item.get('plugin')
        plugin_instance = item.get('plugin_instance')
        type_ = item.get('type')
        type_instance = item.get('type_instance')
        
        # Collectd may send "value" or "values" field, so we gotta handle both cases
        values = item.get('values') or item.get('value')
        if values is None:
            continue
        
        if not isinstance(values, list):
            values = [values]
        
        for value in values:
            obj = {
                "time": time,
                "host": host,
                "plugin": plugin,
                "plugin_instance": plugin_instance,
                "type": type_,
                "type_instance": type_instance,
                "value": value
            }
            measurements.append(obj)
    
    for m in measurements:
        batch_queue.put(m)
    
    return web.Response(text="OK\n")

app = web.Application()
# This would likely have to change for a cleaner setup?
app.add_routes([
    web.post('/', handle),
    web.post('/collectd', handle)
])


async def shutdown_handler():
    """
    Shutdown
    """
    print("\nShutting down gracefully...")
    batch_queue.put(None)  # Signal disk writer to stop
    writer_thread.join()
    sys.exit(0)

def signal_handler():
    asyncio.create_task(shutdown_handler())

if __name__ == "__main__":
    print("Listening for Collectd JSON on http://0.0.0.0:6780/")
    
    try:
        web.run_app(app, host="0.0.0.0", port=6780)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        batch_queue.put(None)
        writer_thread.join()
