#!/bin/bash

if [[ $1 == "debug" ]]; then
  echo "DEBUG mode..."
  docker-compose -f docker-compose.yaml -f debug.override.yaml up -d
else
  docker-compose up -d
fi

docker container logs -f fault_tolerant_dts_master_1
