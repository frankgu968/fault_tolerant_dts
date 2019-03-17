#!/bin/bash

# Rebuild container images
docker build -f ./master/Dockerfile ./master -t scheduler-master-image
docker build -f ./slave/Dockerfile ./slave -t scheduler-slave-image
docker build -f ./utils/Dockerfile ./utils -t seeder-image

# Start docker-compose with either container fs or mapped local fs
if [[ $1 == "debug" ]]; then
  echo "DEBUG mode..."
  docker-compose -f docker-compose.yaml -f debug.override.yaml up -d
else
  docker-compose up -d
fi



# Connect to master logs
docker container logs -f fault_tolerant_dts_master_1
