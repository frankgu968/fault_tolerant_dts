FROM python:3.7.2-alpine3.9

LABEL maintainer="Frank Gu"
LABEL version="1.0"
LABEL description="Container that will erase and seed the scheduler database"

COPY requirements.txt /src/requirements.txt
RUN ["pip", "install", "-r", "/src/requirements.txt"]

COPY seeder.py /src/seeder.py

ENTRYPOINT ["python", "/src/seeder.py"]
