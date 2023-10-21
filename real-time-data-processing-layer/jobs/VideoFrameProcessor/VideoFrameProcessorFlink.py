import os
import cv2
import numpy as np
import base64
import VehicleDetectionTracker
import subprocess
from pyflink.datastream import (
    CheckpointingMode,
    StreamExecutionEnvironment,
    TimeCharacteristic,
)
from pyflink.table.expressions import col, call
from pyflink.table import StreamTableEnvironment, EnvironmentSettings, DataTypes
from pyflink.table.udf import TableFunction, udtf
from logger import Logger

# Kafka configuration using environment variables
KAFKA_INPUT_TOPIC = os.environ.get("KAFKA_INPUT_TOPIC", "input_topic")
KAFKA_OUTPUT_TOPIC = os.environ.get("KAFKA_OUTPUT_TOPIC", "frame_processed")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_GROUP_ID = os.environ.get("KAFKA_GROUP_ID", "flink-consumer-group")
LOGGER = Logger("VideoFrameProcessorFlink")

# Define a custom TableFunction for processing frames
class FrameProcessorTableFunction(TableFunction):

    def __init__(self):
        self.tracker = VehicleDetectionTracker.VehicleTracker()

    def eval(self, mac_address, frame_data):
        # Utility function to decode base64 image data
        def _decode_image(base64_string):
            image_bytes = base64.b64decode(base64_string)
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, flags=cv2.IMREAD_COLOR)
            return image

        # Function to process a single frame
        def _process_frame(frame_data):
            frame = _decode_image(frame_data)
            processed_frame = self.tracker.process_frame(frame)
            return str(processed_frame)
        # Process the frame data and yield the result
        processed_frame = _process_frame(frame_data)
        yield str(processed_frame)

def main():
    """Orchestrates the stream processing engine."""
    LOGGER.info("Starting PyFlink stream processing engine...")
    LOGGER.info(f"KAFKA_INPUT_TOPIC: {KAFKA_INPUT_TOPIC}")
    LOGGER.info(f"KAFKA_OUTPUT_TOPIC: {KAFKA_OUTPUT_TOPIC}")
    LOGGER.info(f"KAFKA_BOOTSTRAP_SERVERS: {KAFKA_BOOTSTRAP_SERVERS}")
    LOGGER.info(f"KAFKA_GROUP_ID: {KAFKA_GROUP_ID}")
    kafka_connectivity_check()
    
    # Get Flink execution environment and table environment
    env, t_env = get_flink_environment()

    # Create source and sink tables
    create_source_table(t_env)
    create_sink_table(t_env)

    # Register the custom FrameProcessorTableFunction as a temporary function   
    t_env.create_temporary_function("frame_processor", udtf(FrameProcessorTableFunction(), result_types=['STRING']))

    # Define the stream processing pipeline
    t_env.from_path("VideoFramesReceived") \
        .select(
            col("mac_address"), 
            col("event_time"), 
            call("frame_processor", 
                 col("mac_address"), 
                 col("frame_data")
                ).cast(DataTypes.STRING())
            ) \
        .execute_insert("VideoFramesProcessed").wait()

    # Execute the Flink program
    env.execute("VideoFrameProcessorFlink")

def kafka_connectivity_check():
    try:
        subprocess.check_call(["apt-get", "update"])
        subprocess.check_call(["apt-get", "install", "kafkacat", "-y"])
        LOGGER.info("kafkacat has been successfully installed.")
        command = ["kafkacat", "-L", "-b", KAFKA_BOOTSTRAP_SERVERS]
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, universal_newlines=True)
        LOGGER.info("Kafka connectivity check result:")
        LOGGER.info(output)
    except subprocess.CalledProcessError as e:
        LOGGER.error("Error during Kafka connectivity check:")
        LOGGER.error(e.output)


def get_flink_environment():
    """
    1. StreamExecutionEnvironment.get_execution_environment(): creates new
    execution environment for Flink that manages the execution of streaming
    data processing jobs.
    """
    env = StreamExecutionEnvironment.get_execution_environment()

    """
    2. env.set_parallelism(1): sets the parallelism of the Flink job to 2,
    which means that all the processing of the streaming data will be done 
    with two threads.
    """
    env.set_parallelism(1)
    """
    3. env.set_stream_time_characteristic(TimeCharacteristic.EventTime): sets
    time characteristic of the streaming data to be event time, which means
    that the processing of events will be based on the timestamp of the events.
    """
    env.set_stream_time_characteristic(TimeCharacteristic.EventTime)
    """
    4. env.enable_checkpointing(10000, CheckpointingMode.EXACTLY_ONCE):
    enables checkpointing for the Flink job every 10 seconds. Checkpointing
    is a mechanism for ensuring fault tolerance in Flink by periodically saving
    the state of the job. The CheckpointingMode.EXACTLY_ONCE ensures that each
    record is processed xactly once, even in the presence of failures.
    """
    env.enable_checkpointing(10000, CheckpointingMode.EXACTLY_ONCE)
    """
    5. env.set_buffer_timeout(5000): sets buffer timeout to 5 seconds. The
    Buffer timeout is the maximum amount of time that a record can be buffered
    before it is processed.
    """
    env.set_buffer_timeout(5000)
    """
    6. t_env = StreamTableEnvironment.create(env): StreamTableEnvironment
    provides a SQL-like interface for processing streaming data. It is used
    for defining tables, queries, and aggregations over streams.
    """
    t_env = StreamTableEnvironment.create(env, environment_settings=EnvironmentSettings.new_instance().in_streaming_mode().build())
    return (env, t_env)


def create_source_table(t_env):
    """
    Create the source table in the Flink table environment.

    Parameters
    ----------
    t_env : StreamTableEnvironment
        The Flink table environment.
    """
    t_env.execute_sql(
        f"""
        CREATE TABLE IF NOT EXISTS VideoFramesReceived (
            mac_address STRING,
            event_time TIMESTAMP(3),
            frame_data STRING,
            WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{KAFKA_INPUT_TOPIC}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP_SERVERS}',
            'properties.group.id' = '{KAFKA_GROUP_ID}',
            'format' = 'json',
            'scan.startup.mode' = 'earliest-offset'
        )
        """
    )

def create_sink_table(t_env):
    """
    Create the sink table in the Flink table environment.

    Parameters
    ----------
    t_env : StreamTableEnvironment
        The Flink table environment.
    """
    t_env.execute_sql(
        f"""
        CREATE TABLE IF NOT EXISTS VideoFramesProcessed (
            mac_address STRING,
            event_time TIMESTAMP(3),
            processed_frame STRING
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{KAFKA_OUTPUT_TOPIC}',
            'properties.bootstrap.servers' = '{KAFKA_BOOTSTRAP_SERVERS}',
            'format' = 'json'
        )
        """
    )

if __name__ == '__main__':
    main()
