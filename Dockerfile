ARG venv_python=3.12
FROM python:${venv_python}

LABEL Maintainer="CanDIG Team"
LABEL "candigv3"="candig-api"

USER root

RUN groupadd -r candig && useradd -r -g candig candig

RUN mkdir -p /home/candig && chown -R candig:candig /home/candig

RUN mkdir /app
WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/candig-api

WORKDIR /app/candig-api

RUN chown -R candig:candig /app/candig-api

USER candig
