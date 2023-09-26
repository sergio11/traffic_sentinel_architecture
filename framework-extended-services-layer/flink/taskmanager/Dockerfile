FROM flink:1.17.1

RUN apt-get update -y && \
    apt-get install -y python3 python3-pip python3-dev && rm -rf /var/lib/apt/lists/*
RUN ln -s /usr/bin/python3 /usr/bin/python

WORKDIR /opt/flink

COPY run-taskmanager.sh .

CMD ["bash", "run-taskmanager.sh"]