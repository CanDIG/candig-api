ARG venv_python
ARG alpine_version
FROM python:${venv_python}-alpine${alpine_version}

LABEL Maintainer="CanDIG Project"
LABEL "candigv2"="<name_of_app>"

USER root

RUN addgroup -S candig && adduser -S candig -G candig

RUN apk update

# add or remove packages that should be installed in the running machine
RUN apk add --no-cache \
	autoconf \
	automake \
	make \
	gcc \
	perl \
	bash \
	build-base \
	musl-dev \
	zlib-dev \
	bzip2-dev \
	xz-dev \
	libcurl \
	linux-headers \
	curl \
	curl-dev \
	yaml-dev \
	pcre-dev \
	git \
	sqlite

COPY requirements.txt /app/<relevant path>/requirements.txt

RUN pip install --no-cache-dir -r /app/<relevant path>/requirements.txt

COPY . /app/<relevant path>

WORKDIR /app/<relevant path>

RUN chown -R candig:candig /app/<relevant path>

USER candig

RUN touch initial_setup

ENTRYPOINT ["bash", "entrypoint.sh"]
