FROM python:3.7.2-alpine3.9

LABEL maintainer="Frank Gu"
LABEL version="1.0"
LABEL description="scheduler-slave container"

RUN apk add --no-cache tini
# Tini is now available at /sbin/tini

# Install Cython for Falcon
RUN apk add --no-cache cython

COPY requirements.txt /src/requirements.txt
RUN ["pip", "install", "-r", "/src/requirements.txt"]

COPY ./ /src

EXPOSE 8888
ENV PYTHONPATH /src

ENTRYPOINT ["/sbin/tini", "-s", "--"]
CMD ["/usr/local/bin/gunicorn", "--bind", "0.0.0.0:8888", "app.start"]
