FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PIP_NO_CACHE_DIR off
ENV PIP_DISABLE_PIP_VERSION_CHECK on
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV COLUMNS 80
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6 libcairo2-dev pkg-config python3-dev build-essential -y

WORKDIR /code/
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt
#COPY  . /code/

#WORKDIR /code/
