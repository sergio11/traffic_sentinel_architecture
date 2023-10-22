from environment import KAFKA_BOOTSTRAP_SERVERS, KAFKA_INPUT_TOPIC, KAFKA_GROUP_ID, KAFKA_OUTPUT_TOPIC
from kafka_connectivity_check import kafka_connectivity_check
from get_flink_environment import get_flink_environment
from create_source_table import create_source_table
from create_sink_table import create_sink_table
from pyflink.table.expressions import col, call
from pyflink.table import DataTypes, Row
from pyflink.table.udf import udtf, TableFunction
from logger import logger
from pyflink.table import Row
from VehicleDetectionTracker.VehicleTracker import VehicleTracker
import base64
import cv2
import numpy as np


class FrameProcessorTableFunction(TableFunction):
    def __init__(self):
        self.tracker = VehicleTracker()

    def eval(self, mac_address, frame_data):
        # Utility function to decode base64 image data
        def _decode_image(base64_string):
            image_bytes = base64.b64decode(base64_string)
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, flags=cv2.IMREAD_COLOR)
            return image

        # Function to process a single frame
        def _process_frame(frame):
            processed_frame = self.tracker.process_frame(frame)
            return str(processed_frame)

        return Row(_process_frame(_decode_image(frame_data)))


def main():
    """Orchestrates the stream processing engine."""
    logger.info("Starting PyFlink stream processing engine...")
    logger.info(f"KAFKA_INPUT_TOPIC: {KAFKA_INPUT_TOPIC}")
    logger.info(f"KAFKA_OUTPUT_TOPIC: {KAFKA_OUTPUT_TOPIC}")
    logger.info(f"KAFKA_BOOTSTRAP_SERVERS: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"KAFKA_GROUP_ID: {KAFKA_GROUP_ID}")
    kafka_connectivity_check()
    
    # Get Flink execution environment and table environment
    env, t_env = get_flink_environment()

    # Register the custom FrameProcessorTableFunction as a temporary function   
    t_env.create_temporary_function("frame_processor", udtf(FrameProcessorTableFunction(), result_types=['STRING']))

    # Create source and sink tables
    create_source_table(t_env)
    create_sink_table(t_env)

    # Define the stream processing pipeline
    t_env.from_path("VideoFramesReceived") \
        .select(
            col("mac_address"), 
            call("frame_processor", 
                 col("mac_address"), 
                 col("frame_data")
                ).cast(DataTypes.STRING())
            ) \
        .execute_insert("VideoFramesProcessed").wait()

    # Execute the Flink program
    env.execute("VideoFrameProcessorFlink")

if __name__ == '__main__':
    main()
