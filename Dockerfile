FROM python:3.11-alpine

WORKDIR /opt/ospf2zabbix

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py .

ENTRYPOINT python3 main.py noisy-triggers --publish
