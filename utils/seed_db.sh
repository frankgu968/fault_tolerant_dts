#!/bin/bash

CONTAINER_NAME=database_seeder

docker build . -t util-seeder
docker rm -f $CONTAINER_NAME
docker run  --network=fault_tolerant_dts_default \
    -e DB_NAME='scheduler_db' \
    -e TASK_COL_NAME='task' \
    -e MONGO_HOST='fault_tolerant_dts_mongo_1' \
    -e MONGO_PORT=27017 \
    -e MONGO_USER='root' \
    -e MONGO_PASSWORD='example' \
    --name $CONTAINER_NAME \
    util-seeder
