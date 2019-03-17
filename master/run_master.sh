#!/bin/bash

NAME=scheduler-master

docker build . -t $NAME-image
docker rm -f $NAME-container
docker run --init -d --network=fault_tolerant_dts_default \
    -e DB_NAME='scheduler_db' \
    -e TASK_COL_NAME='task' \
    -e MONGO_HOST='fault_tolerant_dts_mongo_1' \
    -e MONGO_PORT=27017 \
    -e MONGO_USER='root' \
    -e MONGO_PASSWORD='example' \
    --name $NAME-container \
    -p 8000:8000 \
    $NAME-image