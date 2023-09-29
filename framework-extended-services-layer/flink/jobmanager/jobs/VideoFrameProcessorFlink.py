import os
import VehicleDetectionTracker
from pyflink.datastream.serialization import SerializationSchema
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors import FlinkKafkaConsumer, FlinkKafkaProducer
from pyflink.table import StreamTableEnvironment, DataTypes, EnvironmentSettings
from pyflink.table.window import Tumble
import cv2
import numpy as np
import base64
import json

# Kafka configuration using environment variables
KAFKA_INPUT_TOPIC = os.environ.get("KAFKA_INPUT_TOPIC", "input_topic")
KAFKA_OUTPUT_TOPIC = os.environ.get("KAFKA_OUTPUT_TOPIC", "frame_processed")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_GROUP_ID = os.environ.get("KAFKA_GROUP_ID", "flink-consumer-group")

# Initialize the vehicle tracker
tracker = None

def main():
    global tracker
    tracker = VehicleDetectionTracker.VehicleTracker()

    # Configure PyFlink environment settings
    env_settings = EnvironmentSettings.new_instance().use_blink_planner().build()
    env = StreamExecutionEnvironment.get_execution_environment()
    t_env = StreamTableEnvironment.create(env, environment_settings=env_settings)

    # Define the schema for incoming data
    schema = DataTypes.ROW([
        DataTypes.FIELD("mac_address", DataTypes.STRING()),
        DataTypes.FIELD("timestamp", DataTypes.BIGINT()),
        DataTypes.FIELD("frame_data", DataTypes.STRING())
    ])

    # Kafka properties
    properties = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": KAFKA_GROUP_ID,
        "format": "json"
    }

    # Create a Kafka consumer
    kafka_source = FlinkKafkaConsumer(
        KAFKA_INPUT_TOPIC,
        schema,
        properties=properties
    ).start_from_earliest()

    # Create a Kafka producer for output
    kafka_sink = FlinkKafkaProducer(
        KAFKA_OUTPUT_TOPIC,
        schema,
        producer_config={
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS
        },
        serialization_schema=JsonRowSerializationSchema()
    )

    # Register the Kafka source as a temporary table
    t_env.create_temporary_table("KafkaTable", kafka_source)

    # Define data transformations using PyFlink SQL-like operations
    t_env.from_path("KafkaTable") \
        .select("CAST(mac_address AS STRING) AS mac_address, CAST(timestamp AS BIGINT) AS timestamp, CAST(frame_data AS STRING) AS frame_data") \
        .window(Tumble.over("5.seconds").on("timestamp").alias("w")) \
        .group_by("mac_address, w") \
        .select("process_batch(mac_address, timestamp, COLLECT_LIST(frame_data)) AS processed_payload") \
        .to_append_stream(kafka_sink)

    # Execute the Flink program
    env.execute("VideoFrameProcessorFlink")

# Utility function to decode base64 image data
def _decode_image(base64_string):
    image_bytes = base64.b64decode(base64_string)
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, flags=cv2.IMREAD_COLOR)
    return image

# Function to process a single frame
def _process_frame(mac_address, timestamp, frame_data):
    frame = _decode_image(frame_data)
    processed_frame = tracker.process_frame(frame)
    processed_payload = {
        'mac_address': mac_address,
        'timestamp': timestamp,
        'processed_frame': processed_frame.tolist()  # Convert processed_frame to list for JSON serialization
    }
    return json.dumps(processed_payload)

# Function for batch processing
def process_batch(mac_address, window_start, frame_data_list):
    global tracker
    processed_frames = []
    for frame_data in frame_data_list:
        frame_data = json.loads(frame_data)
        mac_address = frame_data['mac_address']
        timestamp = frame_data['timestamp']
        base64_frame = frame_data['frame_data']
        processed_frame = _process_frame(mac_address, timestamp, base64_frame)
        processed_frames.append(processed_frame)

    return processed_frames

# Custom serialization schema for JSON encoding
class JsonRowSerializationSchema(SerializationSchema):

    def __init__(self):
        pass

    def serialize(self, element):
        return json.dumps(element).encode('utf-8')

if __name__ == '__main__':
    main()
