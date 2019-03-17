#!/bin/bash

NAME=scheduler-slave

docker build . -t $NAME-image
docker rm -f $NAME-container
docker run --init -d --network=fault_tolerant_dts_default \
    -e MASTER_TIMEOUT='5' \
    -e SLAVE_PORT='8888' \
    -e MASTER_HOST='fault_tolerant_dts_master_1' \
    -e MASTER_PORT=8000 \
    -e LOG_LEVEL='DEBUG' \
    -p 8888:8888 \
    $NAME-image