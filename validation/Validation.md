## Test conditions:
- 100 tasks with sleep time between 1 and 20 seconds are seeded
- 3 slaves and 1 master that are randomly taken offline and brought back up

## Events
Following are rough time offsets from when the master was launched for your reference.

|Time Offset(s)|Event|
|-----------|-----|
|00:50.25|Slave 1 down|
|01:16.57|Slave 1 up|
|01:42.7|Master down|
|02:23.31|Master up|
|02:49.42|Slave 2 down|
|03:07.49|Slave 3 down|
|03:36.93|Slave 2 up|
|04:05.66|Slave 3 up|
|07:42.89|Run complete|

#### task83
Unexpected, task83 produced an error that nicely demonstrates the fault recovery of the system.
The events involve 2 slaves:
Slave-1 - Slave with hash 5bf95f787f98cb13ebfa0103a467b60e86bfd0bf
Slave-2 - Slave with hash b2626a253379f3d85ffe4913e4a4c2f95511331d

|Timestamp|Type|Event|
|---------|----|-----|
|23:58:30|INFO|task83 assigned to Slave-2|
|23:58:33|WARN|Slave-2's heartbeat returned an incorrect response code and was removed from the state store. It's task was set to `killed`. Note that due to the asynchronous nature of the slave design, its runner could still be running normally, but the slave has entered an invalid state configuration. |
|23:58:36|INFO|task83 reassigned to Slave-1|
|23:58:37|INFO|Slave-2 make first attempt to contact master API to report "task success", but the master has already removed it from the state record causing the error output. No database state changes were made|
|23:58:38|INFO|Slave-2 reregisters with the master sends first heartbeat response with state `DONE`. Slave-2 transitions back to `READY` state. Master acknowledges the `DONE` state but since Slave-2 is attempting reregistration, master creates a new slave record with state `READY` in the database|
|23:58:46|INFO|Slave-1 completes task83 and notifies master; master updates database|

Since I am nearly out of time, an untested attempt at fixing the problem will be implemented on the `handle-rogue-slave` branch. The above logs are generated from code in release tag `v1.0-rc1`.
