FROM python:3.11-bullseye

WORKDIR /opt/map_shot

RUN apt-get -y update; apt-get install -y chromium

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py .

ENTRYPOINT python map_shot.py
