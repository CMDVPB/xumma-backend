# ### docker compose ###
# FROM python:3.11.4

# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1

# WORKDIR /usr/src/app

# # INSTALL SYSTEM DEPENDANCIES
# RUN apt-get update

# # CREATE STATIC DIRECTORY HERE
# RUN mkdir -p /usr/src/app/static

# COPY ./requirements.txt .

# RUN pip install --upgrade pip

# RUN pip install -r requirements.txt

# COPY . .


### docker compose ###
FROM python:3.11.4

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

# =========================
# System dependencies
# =========================
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    fonts-dejavu \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libfreetype6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# CREATE STATIC DIRECTORY HERE
RUN mkdir -p /usr/src/app/static

COPY ./requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .


