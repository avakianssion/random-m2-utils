#!/usr/bin/env python3.12
"""
Collectd HTTP Plugin Load Generator

Simulates multiple collectd servers sending metrics to your endpoint.

Usage:
    python load_gen.py --servers 100 --rate 10 --duration 60
    python load_gen.py --servers 500 --metrics-per-batch 50 --rate 1


# Simulate 100 servers, each sending 1 req/sec for 60 seconds
python load_gen.py --servers 100 --rate 1 --duration 60

# Simulate 1000 servers with collectd's typical rate (every 10s)
python load_gen.py --servers 1000 --rate 0.1 --duration 120

# High load test: 500 servers, 10 req/sec each
python load_gen.py --servers 500 --rate 10 --duration 30

# Custom endpoint
python load_gen.py --servers 50 --url http://10.0.0.5:8080/metrics
"""

import argparse
import asyncio
import time
import random
from typing import List, Dict
import aiohttp
import orjson


def generate_collectd_metric(hostname: str, plugin: str = None) -> Dict:
    """Generate a realistic collectd metric object"""
    plugins = ["cpu", "memory", "disk", "network", "load"] # random plugins I've seen commonly used
    types = ["gauge", "derive", "counter"] # random types I've seen commonly used
    
    plugin = plugin or random.choice(plugins)
    
    return {
        "host": hostname,
        "plugin": plugin,
        "plugin_instance": str(random.randint(0, 7)),
        "type": random.choice(types),
        "type_instance": "value",
        "time": time.time(),
        "interval": 10.0,
        "values": [random.random() * 100],
        "dstypes": ["gauge"],
        "dsnames": ["value"]
    }


def generate_batch(hostname: str, batch_size: int) -> List[Dict]:
    """Generate a batch of metrics from one server"""
    return [generate_collectd_metric(hostname) for _ in range(batch_size)]


async def send_metrics(
    session: aiohttp.ClientSession,
    url: str,
    hostname: str,
    batch_size: int,
    stats: Dict
):
    """Send one batch of metrics"""
    batch = generate_batch(hostname, batch_size)
    payload = orjson.dumps(batch)
    
    start = time.perf_counter()
    try:
        async with session.post(url, data=payload, headers={"Content-Type": "application/json"}) as resp:
            elapsed = time.perf_counter() - start
            
            if resp.status == 204 or resp.status == 200:
                stats['success'] += 1
                stats['latencies'].append(elapsed)
            else:
                stats['errors'] += 1
                print(f"Error from {hostname}: HTTP {resp.status}")
    except Exception as e:
        stats['errors'] += 1
        print(f"Exception from {hostname}: {e}")


async def server_worker(
    server_id: int,
    url: str,
    rate: float,
    batch_size: int,
    duration: int,
    stats: Dict
):
    """Simulate one collectd server sending metrics at a given rate"""
    hostname = f"host-{server_id:04d}.void.void"
    interval = 1.0 / rate if rate > 0 else 1.0
    
    async with aiohttp.ClientSession() as session:
        end_time = time.time() + duration
        
        while time.time() < end_time:
            await send_metrics(session, url, hostname, batch_size, stats)
            await asyncio.sleep(interval)


async def run_load_test(args):
    """Main load test orchestrator"""
    print(f"Starting load test:")
    print(f"  Servers: {args.servers}")
    print(f"  Rate: {args.rate} requests/sec per server")
    print(f"  Batch size: {args.metrics_per_batch} metrics per request")
    print(f"  Duration: {args.duration} seconds")
    print(f"  Target URL: {args.url}")
    print(f"  Total expected requests: {args.servers * args.rate * args.duration}")
    print()
    
    # Shared stats dictionary
    stats = {
        'success': 0,
        'errors': 0,
        'latencies': []
    }
    
    start_time = time.time()
    
    # Launch all server workers
    tasks = [
        server_worker(i, args.url, args.rate, args.metrics_per_batch, args.duration, stats)
        for i in range(args.servers)
    ]
    
    await asyncio.gather(*tasks)
    
    elapsed = time.time() - start_time
    
    # Print results
    print("\n" + "="*60)
    print("LOAD TEST RESULTS")
    print("="*60)
    print(f"Total time: {elapsed:.2f}s")
    print(f"Successful requests: {stats['success']}")
    print(f"Failed requests: {stats['errors']}")
    print(f"Total requests: {stats['success'] + stats['errors']}")
    print()
    
    if stats['latencies']:
        latencies = sorted(stats['latencies'])
        print(f"Latency stats (seconds):")
        print(f"  Min: {min(latencies)*1000:.2f}ms")
        print(f"  Max: {max(latencies)*1000:.2f}ms")
        print(f"  Mean: {sum(latencies)/len(latencies)*1000:.2f}ms")
        print(f"  p50: {latencies[len(latencies)//2]*1000:.2f}ms")
        print(f"  p95: {latencies[int(len(latencies)*0.95)]*1000:.2f}ms")
        print(f"  p99: {latencies[int(len(latencies)*0.99)]*1000:.2f}ms")
    
    total_metrics = stats['success'] * args.metrics_per_batch
    print()
    print(f"Throughput:")
    print(f"  {stats['success']/elapsed:.2f} requests/sec")
    print(f"  {total_metrics/elapsed:.2f} metrics/sec")


def main():
    parser = argparse.ArgumentParser(
        description="Load test collectd HTTP endpoint",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--servers",
        type=int,
        default=10,
        help="Number of simulated servers"
    )
    
    parser.add_argument(
        "--rate",
        type=float,
        default=1.0,
        help="Requests per second per server (collectd default is ~0.1, or 1 per 10s interval)"
    )
    
    parser.add_argument(
        "--metrics-per-batch",
        type=int,
        default=20,
        help="Number of metrics per batch (collectd typically sends 10-50)"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Test duration in seconds"
    )
    
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8080/collectd",
        help="Target endpoint URL"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_load_test(args))
    except KeyboardInterrupt:
        print("\nTest interrupted by user")


if __name__ == "__main__":
    main()
