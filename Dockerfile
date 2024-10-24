# syntax=docker.io/docker/dockerfile:1.7-labs

FROM ubuntu:focal

# Prevent popups during install of requirements
ENV DEBIAN_FRONTEND=noninteractive

# App Requirements
RUN apt update -qq && apt install -y -qq git build-essential gdb lcov pkg-config \
    libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev \
    libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev \
    lzma lzma-dev python3-tk tk-dev uuid-dev zlib1g-dev && rm -rf /var/lib/apt/lists/*

# pyenv for guaranteed py 3.12
ENV HOME="/root"
WORKDIR ${HOME}
RUN apt update && apt install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl https://pyenv.run | bash
ENV PYENV_ROOT="${HOME}/.pyenv"
ENV PATH="${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${PATH}"

# Ensure tkinter
ENV PYTHON_CONFIGURE_OPTS "--enable-shared"

# install py 3.12
ENV PYTHON_VERSION=3.12.6
RUN pyenv install --verbose ${PYTHON_VERSION}
RUN pyenv global ${PYTHON_VERSION}

WORKDIR /usr/src/app
ENTRYPOINT ["sh", "-c", "pip install --no-cache-dir .[build] && pyinstaller ou_dedetai.spec"]
