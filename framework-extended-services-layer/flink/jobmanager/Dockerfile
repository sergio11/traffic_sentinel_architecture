FROM flink:1.17.1

# Custom image specifically tailored for running Apache Flink with Python-based jobs (PyFlink).

# install python3 and pip3
RUN apt-get update -y && apt-get install ffmpeg libsm6 libxext6 -y && \
apt-get install -y python3 python3-pip python3-dev && rm -rf /var/lib/apt/lists/*
RUN ln -s /usr/bin/python3 /usr/bin/python

WORKDIR /opt/flink

COPY requirements.txt .
# Install Python dependencies from requirements.txt
RUN pip3 install -r requirements.txt

CMD ["bash", "run.sh"]