import os
import cv2
import numpy as np
import base64
import VehicleDetectionTracker
from pyflink.datastream import (
    CheckpointingMode,
    StreamExecutionEnvironment,
    TimeCharacteristic,
)
from pyflink.table.expressions import col, lit
from pyflink.table import StreamTableEnvironment, EnvironmentSettings
from pyflink.table.udf import TableFunction, udtf
from logger import Logger

# Kafka configuration using environment variables
KAFKA_INPUT_TOPIC = os.environ.get("KAFKA_INPUT_TOPIC", "input_topic")
KAFKA_OUTPUT_TOPIC = os.environ.get("KAFKA_OUTPUT_TOPIC", "frame_processed")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_GROUP_ID = os.environ.get("KAFKA_GROUP_ID", "flink-consumer-group")
LOGGER = Logger("VideoFrameProcessorFlink")


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
            return processed_frame

        processed_frame = _process_frame(frame_data)
        yield processed_frame

def main():
    """Orchestrates the stream processing engine."""
    LOGGER.info("Starting PyFlink stream processing engine...")
    
    env, t_env = get_flink_environment()
    # Create source and sink tables
    create_source_table(t_env)
    create_sink_table(t_env)

    t_env.create_temporary_function("frame_processor", udtf(FrameProcessorTableFunction(), result_types=['STRING']))

    # Define the SQL query with the custom aggregation function.
    sql_query = f"""
        SELECT
            mac_address,
            frame_processor(mac_address, frame_data) AS processed_payload
        FROM
            VideoFramesReceived
    """

    LOGGER.info(sql_query)

    # Execute the SQL query and send the results to the "VideoFramesProcessed" stream.
    t_env.execute_sql(sql_query).to_append_stream("VideoFramesProcessed", output_mode="append")

    # Execute the Flink program
    env.execute("VideoFrameProcessorFlink")


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
            frame_timestamp BIGINT,
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
