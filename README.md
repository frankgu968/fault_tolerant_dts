# Fault Tolerant Distributed Task Scheduler
Author: Frank Gu  
Date: Mar 17, 2019

## Usage
To run the stack, simply run `run.sh` in the source directory :)

This script will create the mongodb, 1 master and 3 slaves, and seed the mongodb with 100 tasks with random sleeptimes between 1 and 20 seconds.  
The master's API server is exposed on `http://localhost:8000`.  
The scheduler is started by default, but you can start/stop the scheduler manually by making a HTTP POST to `http://localhost:8000/scheduler/[start | stop]`

## Overview
This proof-of-concept fault tolerant distributed task scheduler is composed of **three** components:                

1. **Master**  
The master is responsible for maintaining the system state view, scheduling tasks, and managing the database connection. The slave states (eg. state, hostname) are stored in a mongodb collection; the master will create this metadata collection if it doesn't already exist, or pick up from another master's system state view for fault recovery.
2. **Slave(s)**  
The slaves register with the master and executes the task assigned by the master at a given time. Task execution is independent of the master's existence. If a master is determined to be offline, the slave will simply preserve its execution state and wait for coordination from a new master.
3. **Metadata Store**
The metadata store is implemented as two collections in a mongodb instance. The `task` collection contains documents that represent individual tasks in any state. The `slaves` collection contains documents used by the master to keep track of the slave states.

See the `validation` directory for run results. 

#### Requirements
- The metadata store shall be *mongodb*
- Master and slave(s) shall be written in Python and run in a containerized environment
- The master and slave shall be fault tolerant:
  - Terminating the master at any given point shall not affect slaves running tasks. Jobs will continue running on slaves to completion, and remain in that state until further contact with a new master
  - Terminating any slaves will terminate the task running on the slave
- Tasks running on the slaves are atomic
- Only the master has access to the database
- Master and slave activities shall be logged with timestamps and identifiers

#### Design assumptions
1. Timing is not critical; scheduling offsets and drifts on the order of hundres of milliseconds can be tolerated
2. The system is run in an environment that supports basic container networking:
  - Has a system-wide DNS for containers at least
  - Supports HTTP application protocol
  - Has WWW network access
3. Tasks are atomic and indempotent: can be run multiple times and only "succeed" when the task is run to completion
4. Slave(s) and master will remain online independent of tasks in the system
5. System is automated and will run all queued tasks
6. User has simple start/stop access to master; but cannot access slave
7. System shall be robust to a *reasonable* degree of input error
8. Each slave will be run on the same container port, and on unique hostnames

## Design
Conforming with modern microservice-based architectures, the master and slave(s) will communicate with each other using a REST-ish API interface; for simplicity, full RESTful compliance is not intended. All three components of the system are run in docker containerized environments with all source and dependencies preinstalled. Master and slave images are based on the Alpine Linux python image with Cython for higher performance.

### Container init
Both the master and slave are designed to run multiple workloads and  loops (eg. timers, API server). Due to the use of threading (for the loops and timers) and subprocesses (as the task runner), `Tini` is included in each container to as the minimal init-system and reap zombie processes.

### API Server
The master's and slave's API server are their only means of communication with each other. In a production environment, high-volume traffic (especially on the master) should be expected. Therefore, it's vital to design a high-performing stack.

The API server uses the `falcon` framework run on a `gunicorn` WSGI server.  
In the initial design phase, I have considered using Flask and Bottle with an uWSGI server to provide the API services since they are relatively well-performing and I am familiar with their design patterns. However, the synthetic benchmarks ([here](http://klen.github.io/py-frameworks-bench/), [officially](https://falconframework.org/), [here](https://blog.appdynamics.com/engineering/a-performance-analysis-of-python-wsgi-servers-part-2/), and [here](https://github.com/the-benchmarker/web-frameworks)) suggest that Falcon + Gunicorn is a good combination with relatively high performance and stability.  

Falcon also offers a nice ORM abstraction.

### Metadata Store (mongodb)
No validation has been built-in at this point due to lack of time; though this may be a good idea to ensure database integrity in the future. The master uses the `mongoengine` database connector as a high-level abstraction interface and to mitigate simple schema errors.

##### Task Schema
```
{
  "taskname": String(required),
  "sleeptime": String(required),
  "state": String(required),
  "host": String(optional),
}
```
##### Slave Schema
```
{
  "hash": String(required),
  "url": String(required),
  "state": String(required)
}
```
The slave schema's `hash` field is automatically by a creation hook as a SHA-1 hash of the slave's `url` that the system uses to uniquely identify each slave. The alphanumeric hash allows for great extensibility in the future allowing it to be directly included as URL arguments. The document's ObjectID was not used in consideration of potential security risks in a networked environment.

### Master
The master's entrypoint is Gunicorn, which instantiates the API server and its classes. The `SchedulerResource` class then instantiates the `Scheduler` class, which creates and starts the scheduler. See below for detailed scheduler description.

##### Scheduler
The main component of the master is its scheduler. It exposes a few helper functions to the API server to facilitate slave and task state transitions, and runs two loops:
1. **scheduler_loop**
```
loop custom-scheduler-interval:
      is there a task to be run (ie. state='created' or 'killed')?  
          is there a slave to run the task (ie. state='READY')?  
              POST the entire task description to the slave  
```

2. **heartbeat_loop**
```
loop custom-heartbeat-interval:
      for a_slave in collection(slave):  
          response = POST to a_slave.url  
          if response is not HTTP_OK:
              remove a_slave from collection(slave)
              remove any task from collection(task) where state='running' and host='a_slave.hash'  
          else:
              reset a_slave's heartbeat timer
```
Each slave has its own heartbeat timer and is set/reset independently from other slaves. The heartbeat timer is given a `heartbeat_grace_period` (default: 2s) to allow for network delay and timing drifts. The slave(s) respond to the heartbeat requests with their latest states. The master will check the slave's states and perform the necessary updates to the metadata store accordingly.

  The slave and its associated task(s) are removed from the metadata store under any of these conditions:  
    - Heartbeat timeout
    - Incorrect response code from either heartbeat or task scheduling
    - Network timeout
    - Network error  

  **Note**: current implementation does not allow for backoffs of any kind. If the slave is deemed *possibly* unreliable, then it will be removed from the master's metadata state view. This ensures that all tasks are run atomically trading off speed/efficiency for system integrity.

Threading was uses as the parallelization strategy since both loops needed to share the scheduler's `mongoengine` database connector, which becomes unsafe to use post-fork.

### Slave
The slave is simply an API server that responds to the master's heartbeat requests and task assignments.

##### State machine
The slave implements a simple state-machine that transitions between the `INIT`, `READY`, `RUNNING`, and `DONE` states.

##### Master timeout
To correctly recover from master failures, the slave also implements a customizable master timeout that will invoke the appropriate actions for the slave to attempt reconnection with the master.  
On slave start-up or master timeout, the slave will call its `register` function that transmits the slave's states to the known master URL. If a previously running task on a slave is completed, the slave will be transitioned to the **DONE** state. When the new master comes online and receives the registration attempt from the slave with a state **DONE**, it will update the metadata store by setting the task's state to *`success`* and the slave's state to *`READY`*. If the slave receives a HTTP 200 OK status from the master in this state, it will transition back to the *`READY`* state internally.   

*There is a possible failure mode in which the master goes offline after writing the slave's `READY` state to the database and never responds with the HTTP 200 OK message, resulting in an out-of-sync state view. This situation is remedied by the master's aggressive heartbeat policy, by which on the next heartbeat request, the slave will broadcast the **DONE** state again and repeat the cycle until the slave's internal state and the master's state views are synchronized.*

##### Runner
On master task assignment POST, the API server will spool a thread, which forks a subprocess running the `sleep` command. The thread, which has access to the slave attributes, acts as the monitor for the process and updates the slave's state(s) accordingly. The process can then be safely forked from the slave and run isolated.

## Future Work 
This repository is missing automated tests. I had spent a tad too long researching and familiarizing myself with the frameworks (hadn't worked with Falcon and mongoengine before...) and ran out of time to implement the them. The functionality of the current codebase is tested manually, but the automation should be implemented for future extensibility. 

This setup would ideally be deployed onto a Kubernetes cluster with a "Deployment" of slave pods (replica: 3) and a Deployment of the master with the master container and mongodb container in 1 pod for tight coupling. The slaves can then be exposed by a ClusterIP service to the master. The master API can be exposed externally through a NodePort or LoadBalancer depending on cloud provider. 

## API Reference
### Master
##### Path: /scheduler/start
Action: POST  
Body: {}  
Response:
- **HTTP 200**  
  Conditions: Scheduler has successfully started  
  Body {"message": "Scheduler has started..."}

- **HTTP 400**  
  Conditions: Scheduler already running, no change to master  
  Body {"error": "Scheduler is already running!"}

##### Path: /scheduler/stop
Action: POST  
Body: {}  
Response:
- **HTTP 200**  
  Conditions: Scheduler has successfully stopped  
  Body {"message": "Scheduler has stopped."}

- **HTTP 400**  
  Conditions: Scheduler was not running, no change to master  
  Body {"error": "Scheduler was not running!"}

##### Path: /scheduler/task_done
Action: POST  
Body:
```
{
  "hash": String(required),
  "url": String(required),
  "state": String(required),
  "task": TaskJSON(required)
}
```  
Response:
- **HTTP 200**  
  Conditions: Task completion successfully reported to master. Slave state set to `READY`; Task state set to `success`.  
  Body {"message": "Scheduler has stopped."}

- **HTTP 400**  
  Conditions: Scheduler was not running, no change to task and slave
  Body {"error": "Master scheduler was not running!"}  

##### Path: /slave
Action: POST  
Body: {"url": String(required)}  
Response:
- **HTTP 200**  
  Conditions: Updated slave state or created new slave entry in database  
  Body {SlaveJSON}

- **HTTP 400**  
  Conditions: Attempted to add duplicate entry into database  
  Body {"error": "Slave URL already exists"}

### Slave
##### Path: /
Action: GET  
Body: {}  
Response:
- **HTTP 200**  
  Conditions: Successfully got slave state
  Body {SlaveJSON}

##### Path: /
Action: POST  
Body: {TaskJSON}  
Response:
- **HTTP 200**  
  Conditions: Slave begins running task
  Body {SlaveJSON}

- **HTTP 400**  
  Conditions: Slave error; could not run task


## Container Reference
### Master
##### Environment variables
|Variable|Purpose|Default|
|--------|-------|-------|
|LOG_LEVEL|Change the log level|DEBUG|
|SLAVE_COL_NAME|Slave collection name|slave|
|TASK_COL_NAME|Task collection name|task|
|SCHEDULE_INTERVAL|Scheduler loop period|5|
|HEARTBEAT_INTERVAL|Heartbeat loop period|3|
|HEARTBEAT_GRACE_PERIOD|Heartbeat grace period|2|
|DB_NAME|Database name|scheduler_db|
|MONGO_USER|MongoDB username|root|
|MONGO_PASSWORD|MongoDB password|example|
|MONGO_HOST|MongoDB hostname|localhost|
|MONGO_PORT|MongoDB port|27017|

### Slave
##### Environment variables
|Variable|Purpose|Default|
|--------|-------|-------|
|LOG_LEVEL|Change the log level|DEBUG|
|MASTER_HOST|Master hostname|localhost|
|MASTER_PORT|Master port|8000|
