# ### docker compose ###
# FROM python:3.11.4

# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1

# WORKDIR /usr/src/app

# # =========================
# # System dependencies
# # =========================
# RUN apt-get update && apt-get install -y \
#     wkhtmltopdf \
#     fonts-dejavu \
#     libxrender1 \
#     libxext6 \
#     libfontconfig1 \
#     libfreetype6 \
#     && apt-get clean \
#     && rm -rf /var/lib/apt/lists/*

# # CREATE STATIC DIRECTORY HERE
# RUN mkdir -p /usr/src/app/static

# COPY ./requirements.txt .

# RUN pip install --upgrade pip \
#     && pip install -r requirements.txt

# COPY . .


### docker compose ###
FROM python:3.11.4

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

# =========================
# System dependencies (REQUIRED for GeoDjango)
# =========================
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    proj-data \
    proj-bin \
    wkhtmltopdf \
    fonts-dejavu \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libfreetype6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# IMPORTANT: tell pip / Django where GDAL is
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

RUN mkdir -p /usr/src/app/static

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .