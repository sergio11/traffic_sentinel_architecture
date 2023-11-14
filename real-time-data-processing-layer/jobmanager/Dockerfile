# Use the official Apache Flink base image
FROM flink:1.17.1

# Install Python3 and required packages
RUN apt-get update -y && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    python3 \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a symbolic link for Python3
RUN ln -s /usr/bin/python3 /usr/bin/python

# Set the working directory to the Flink installation directory
WORKDIR /opt/flink

# Install Apache Flink dependencies
RUN pip install apache-flink==1.18.0
RUN pip install apache-flink-libraries==1.18.0

# Copy connectors from the connectors directory
COPY ../connectors/flink-connector-kafka-1.17.1.jar ./lib/
COPY ../connectors/kafka-clients-3.5.1.jar ./lib/

# Define the default command to run your Python-based Flink job
CMD ["bash", "run.sh"]