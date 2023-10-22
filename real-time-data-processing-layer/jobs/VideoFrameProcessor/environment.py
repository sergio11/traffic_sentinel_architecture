import os

# Kafka configuration using environment variables
KAFKA_INPUT_TOPIC = os.environ.get("KAFKA_INPUT_TOPIC", "input_topic")
KAFKA_OUTPUT_TOPIC = os.environ.get("KAFKA_OUTPUT_TOPIC", "frame_processed")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_GROUP_ID = os.environ.get("KAFKA_GROUP_ID", "flink-consumer-group")