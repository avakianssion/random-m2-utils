# The Tokio Rust Crate

- Tokio is a runtime for writing reliable network applications without compromising speed.
- Non Blocking I/O
- Asynchronous
- Used for TCP/UDP sockets, filesystem operations, and process and signal management.

## Tasks
- Async programs in Rust use non-blocking execution units called tasks. 
- Tokio has a ```spawn``` function and ```JoinHandle``` type. Using these, we schedule tasks on the Tokio runtime and await the output of the spawned task. 
- ```Tokio::time``` gives us tools to manage timeouts for tasks.

## CPU-bound tasks
- Tokio is able to do concurrent work by swapping running tasks on each thread. However, this swapping only happens at the ```.awat``` point. If your code spends a long time before reaching this point, the swapping will not speed things up as much.
- Core threads - Where all async code runs, Tokio spawns one for each CPU core. This could be overriden with ```TOKIO_WORKER_THREADS```
- Blocking threads - Spawned on demand using ```thread_keep_alive```. 
- For CPU-heavy tasks that need to be parallel, the Tokio docs recommend looking into the ```rayon``` library.

## Async IO
As well as scheduling and running tasks, Tokio provides everything you need to perform input and output asynchronously.
