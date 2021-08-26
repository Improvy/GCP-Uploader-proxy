FROM ubuntu:20.04

RUN apt-get update && apt-get install --no-install-recommends -y python3 python3-pip
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -q -r /tmp/requirements.txt

ADD ./web /opt/web/
WORKDIR /opt/web

ENV FLASK_APP /opt/web/app.py

CMD gunicorn --timeout 360 --bind 0.0.0.0:$UPROXY_PORT -k gevent --worker-connections 32 app:app