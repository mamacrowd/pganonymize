FROM python:3.8.1-slim

LABEL maintainer="webteam@rheinwerk-verlag.de"

RUN apt-get update -y \
 && apt-get upgrade -y \
 && apt-get install -y libpq-dev python3-pip \
 && pip install -U pip \
 && pip install psycopg2-binary \
 && python setup.py install \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
