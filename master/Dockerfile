FROM python:3.7.2-alpine3.9

LABEL maintainer="Frank Gu"
LABEL version="1.0"
LABEL description="scheduler-master container"

COPY requirements.txt /src/requirements.txt
RUN ["pip", "install", "-r", "/src/requirements.txt"]

COPY ./ /src

ENTRYPOINT ["python", "/src/master.py"]
