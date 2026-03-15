# Zen of Python - A collection of 19 guiding principles to write 'Pythonic' code.
```
        The Zen of Python, by Tim Peters

        Beautiful is better than ugly.
        Explicit is better than implicit.
        Simple is better than complex.
        Complex is better than complicated.
        Flat is better than nested.
        Sparse is better than dense.
        Readability counts.
        Special cases aren't special enough to break the rules.
        Although practicality beats purity.
        Errors should never pass silently.
        Unless explicitly silenced.
        In the face of ambiguity, refuse the temptation to guess.
        There should be one-- and preferably only one --obvious way to do it.
        Although that way may not be obvious at first unless you're Dutch.
        Now is better than never.
        Although never is often better than *right* now.
        If the implementation is hard to explain, it's a bad idea.
        If the implementation is easy to explain, it may be a good idea.
        Namespaces are one honking great idea -- let's do more of those!
```

# Reference - Hitchhiker's Guide to Python
https://docs.python-guide.org/writing/style/

# *** Read This First ***
The following are guidelines, not hard rules.
While the concepts and practices here reflect modern, high-performance Python engineering, simplicity always comes first.
Developers should apply these recommendations judiciously, guided by real profiling data, clarity of design, and maintainability.
Over-optimization is often more dangerous than under-optimization. The goal is clean, predictable, and observable performance, not clever Code Golf.

# A Few Performance Oriented Concepts and Tools
## Concurrency and Parallelism
### Python Global Interpreter Lock (GIL)
The Python Global Interpreter Lock or GIL, in simple words, is a mutex (or a lock) that allows only one thread to hold the control of the Python interpreter.

This means that only one thread can be in a state of execution at any point in time. The impact of the GIL isn’t visible to developers who execute single-threaded programs, but it can be a performance bottleneck in CPU-bound and multi-threaded code.

### Threads
Provides an interface to OS-level threads. Because of the GIL, CPU-bound work remains largely serialized.Threading will not speed up heavy computation. Use it for parallel execution of blocking I/O operations (e.g., network or file APIs) and when you need fine-grained control over thread behavior. 
Threads are not free! Each one consumes stack memory and OS scheduling overhead so large-scale concurrency (hundreds or thousands of tasks) is better handled with asynchronous I/O or multiprocessing. For most cases, you should avoid creating threads manually and instead use ```concurrent.futures.ThreadPoolExecutor```, which manages a pool of reusable worker threads and simplifies task submission and cleanup.
### Multiprocessing
The ```multiprocessing``` module provides an interface for spawning independent Python processes using an API deliberately similar to threading. Unlike threads, each process runs in its own Python interpreter and memory space, which means it is not constrained by the GIL. This allows true parallel execution across multiple CPU cores.

Because processes do not share memory by default, you cannot directly access or modify objects across processes. Communication must occur through multiprocessing primitives such as Queue, Pipe, or shared memory constructs. This adds a layer of complexity that needs to be carefully managed.

For most applications, prefer using concurrent.futures.ProcessPoolExecutor, which simplifies process management and automatically handles the creation, reuse, and cleanup of worker processes.

### AsyncIO
The ```asyncio``` framework provides cooperative, single-threaded concurrency built around non-blocking I/O and coroutines. Unlike threading or multiprocessing, which rely on OS-level parallelism, asyncio runs all tasks within a single event loop that switches between them whenever one is waiting for I/O. This allows many concurrent operations to coexist without the overhead of threads or processes.

AsyncIO code is written using coroutines defined with ```async def```, and uses await to suspend execution while waiting for an operation to complete. Keep in mind that suspending is different from blocking. Suspending gives control back to the event loop, allowing other tasks to make progress in the meantime. The only truly blocking part of an asyncio program is typically the ```asyncio.run()`` call that starts the event loop.

Because everything must be non-blocking, asyncio works best with async-native libraries like ```aiohttp``` and is ideal for highly concurrent I/O-bound applications. Be aware that the syntax of this framework is not very intuitive and the level of complexity is not always worth the milliseconds or cpu cycles saved.

### Thread and Process Pools
Both threads and processes can be managed individually and in some cases should be. However, in most production code, it’s more efficient and maintainable to use a ```pool```: a group of pre-initialized workers that execute submitted tasks. Python provides these through ```concurrent.futures.ThreadPoolExecutor``` and ```concurrent.futures.ProcessPoolExecutor```. [The ```Concurrent Execution``` section in docs.python.org is a very useful tool for understanding these concepts deeper.]

A pool handles the lifecycle of its workers: it creates a fixed number of threads or processes, queues incoming work, and reuses workers for multiple tasks. This minimizes the overhead of repeatedly creating and destroying threads or processes, which can be expensive. It also prevents the system from being overwhelmed by unbounded concurrency, since the pool limits how many workers can run at once.

Using a pool is generally safer and cleaner than manually spawning workers and dare I say, easier on the eye. The pool API abstracts away synchronization, exception handling, and result collection through a simple ```submit()``` or ```map()``` interface that returns Future objects. These futures can be awaited, cancelled, or checked for completion without manually joining or tracking worker lifetimes. Due to this abstraction, however, the programmer has to take some extra care to properly log or not log some exceptions.

Thread pools are ideal for I/O-bound workloads, where tasks mostly wait for external resources and the GIL is not a bottleneck. Process pools are great for CPU-bound workloads, as each process has its own Python interpreter and runs in true parallel (See previous section on the pros/cons of processes).

## Memory Layout and Performance: Flat vs. Container Objects in Python
When working with data structures in Python, understanding how objects are represented in memory is essential. Python’s data types can generally be categorized as either flat or container objects, and this distinction has major implications for performance, cache behavior, and memory usage.

In Python, flat objects store their data contiguously in memory, while container objects store references (pointers) to other Python objects scattered across the heap. Examples of flat objects include bytes, bytearray, memoryview, and str, which behave like C arrays—compact, cache-friendly, and efficient for sequential or binary operations. Containers like list, tuple, dict, and set instead manage collections of object references, offering flexibility at the cost of extra memory overhead and pointer indirection.

From a performance standpoint, flat objects are faster for ETL pipelines and dataflow processing because their contiguous layout minimizes cache misses and reduces per-element Python object overhead. Containers, while more expressive and dynamic, suffer from slower iteration and higher allocation cost.
## Error Handling
TODO

## Logging
TODO

## Profiling
TODO

### CPU Profiling (cProfile)
TODO

### Memory Profiling
TODO

### System Level Metrics (psutil)
TODO