FROM python:3.8-slim

RUN apt-get update && \
    apt-get install -y iproute2

COPY . /app

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "fog_node.py"]