# syntax=docker/dockerfile:1

FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt tlstester.py entrypoint.sh ./

RUN pip3 install -r requirements.txt

EXPOSE 4300-4349

CMD ./entrypoint.sh

