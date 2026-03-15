# Systemd
## Basics
### Introduction
- Systemd, at its core, is an init system. This is the most important process of all when you start up, it always gets PID 1 because its job is to manage all other processes.
- The systemd init system was built by Lennart Poettering in 2010. Source code is of course in C. (https://github.com/systemd/systemd)
### Units
- Anything systemd is able to manage for you is a unit. These include services, timers, mounts, automounts, and more.
### Basic Commands
- To check the status of a unit we can run ```systemctl status <name-of-unit>```
- When a service is ```disabled```, it means it will not start on startup. For a service to start on startup, you need to run ```systemctl enable <name-of-unit>```
- We can also, of course, ```start, stop, restart``` services with the same format.
- Fun fact - Red had based distributions will NOT enable the service for you when you install it, while distributions like Debian and Ubuntu would.
- Status will usually give you logs at the end of the standard out, including error messages. Keep in mind that your user will only see the messages you are allowed to see.
- RECAP: ```start stop restart status enable disable``` Are the main 6 commands you will need 90% of the time.
### Unit Files
- As already covered, entities managed by systemd are called units. units are managed through files for each unit.
- Directories that are most common for these files are: ```/etc/systemd/system, /run/systemd/system, /lib/systemd/system```
- ```etc``` is going to be the most high priority followed by ```run``` and ```lib``` and systemd will treat them as such. The priority determines what gets loaded into memory first.
- ```/user/lib/systemd/system``` - Maintainer - rpms use this
- ```/etc/systemd/system``` - Administrator
- ```/run/systemd/system``` - Non-persistent
- Service files are very common but there are other types of units: 
  - .service
  - .socket
  - .device
  - .mount
  - .automount
  - .swap
  - .target
  - .path
  - .timer
  - .slice
  - .scope
  - .snapshot
  - .busname
- For the most part, a unit file will have three primary sections: ```unit, service, and install```
- Unit files are case sensitive, so the setup shall not be messed with.
- The Unit section will contain general information about the unit. Things like ```description``` or ```Wants``` which is essentially a pre-requisite list. 
- Under the ```Service``` section you will have some options including Type. This section defines the behavior of the service. Type has many options, including ```simple, forking, oneshot, dbus, notify, idle```. Simple is the default, where the processes started by ```ExecStart``` is the main process of the service.
- Also important to know about ```reload```. When the configuration file changes, for some changes, you don't have to restart the service, reload will load in the new configs. 
- The ```Install``` section has to do with dependency relationships. Something like ```multi-user.target``` being set for the Install section means the service will not start until multiple users are able to user the system.
- To make changes to the files, you can of course vim into the file, but you can also run ```systemctl edit <name-of-unit>```. This method will create an override file. When you save this file, your changes will be merged with the existing file. 
#
## Beyond the Basics
- Systemd keeps track of kernel control groups for each process that starts and all processes forked from that processes. That's how it is able to cleanly kill a service.
- List Loaded services ``` systemctl -t service```
- List installed services ```systemctl list-unit-files -t service```
- Check for services in failed state ```systemctl --state failed```
- Targets == Runlevels
- There is also a GUI for some reason called Cockpit.
- Timers - a native crontab functionality.
  ```
  [Timer]
  onStartupSec=10min
  ```
- Handling out-of-memory (OOM) condition
  ```
  [Service]
  # Memory and OOM handling
  MemoryMax=50G
  OOMPolicy=kill           # Kill all processes in the cgroup on OOM
  Restart=on-failure       # Restart automatically after OOM
  RestartSec=5s            # Wait 5 s before restart

  # Core dump support
  LimitCORE=infinity       # Allow core dumps
  Environment=SYSTEMD_COREDUMP=1
  ```
- Another cool tool systemd offers is ```systemd cg-top```. It's basically top but for control groups systemd is managing.