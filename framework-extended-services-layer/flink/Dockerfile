FROM flink:1.17.1

# install python3 and pip3
RUN apt-get update -y && \
apt-get install -y python3 python3-pip python3-dev && rm -rf /var/lib/apt/lists/*
RUN ln -s /usr/bin/python3 /usr/bin/python
WORKDIR /opt/flink

COPY VehicleDetectionTracker.py .
COPY VideoFrameProcessorFlink.py .
COPY run.sh .
COPY requirements.txt .

# Install Python dependencies from requirements.txt
RUN pip3 install -r requirements.txt

CMD ["bash", "run.sh"]