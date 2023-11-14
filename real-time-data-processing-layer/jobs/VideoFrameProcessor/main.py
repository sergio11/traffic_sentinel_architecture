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
from VehicleDetectionTracker.VehicleDetectionTracker import VehicleDetectionTracker


class FrameProcessorTableFunction(TableFunction):
    """
        Initializes the FrameProcessorTableFunction.

        Args:
            tracker: An instance of the vehicle tracker used for processing frames.
    """
    def __init__(self, tracker):
        self.vehicle_tracker = tracker

    def eval(self, frame_data, timestamp):
        """
        Evaluates the FrameProcessorTableFunction for the given frame data and timestamp.

        Args:
            frame_data (str): Base64-encoded frame data.
            timestamp: The timestamp associated with the frame.

        Returns:
            Row: A Row containing the result of processing the frame with the vehicle tracker.
        """
        # Process the frame using the vehicle tracker and return the result as a Row
        return Row(str(self.vehicle_tracker.process_frame_base64(frame_data, timestamp)))


def main():
    """Orchestrates the stream processing engine."""
    logger.info("Starting PyFlink stream processing engine...")
    logger.info(f"KAFKA_INPUT_TOPIC: {KAFKA_INPUT_TOPIC}")
    logger.info(f"KAFKA_OUTPUT_TOPIC: {KAFKA_OUTPUT_TOPIC}")
    logger.info(f"KAFKA_BOOTSTRAP_SERVERS: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"KAFKA_GROUP_ID: {KAFKA_GROUP_ID}")
    kafka_connectivity_check()

    # Create vehicle detection tracker instance
    vehicleTracker = VehicleDetectionTracker()

    # Get Flink execution environment and table environment
    env, t_env = get_flink_environment()

    # Register the custom FrameProcessorTableFunction as a temporary function   
    t_env.create_temporary_function("frame_processor", udtf(FrameProcessorTableFunction(vehicleTracker), result_types=['STRING']))

    # Create source and sink tables
    create_source_table(t_env)
    create_sink_table(t_env)

    # Define the stream processing pipeline
    t_env.from_path("VideoFramesReceived") \
        .select(
            col("mac_address"), 
            col("camera_id"),
            col("frame_timestamp"),
            call("frame_processor", 
                col("frame_data"),
                col("frame_timestamp") 
            ).cast(DataTypes.STRING())
            ) \
        .execute_insert("VideoFramesProcessed").wait()

    # Execute the Flink program
    env.execute("VideoFrameProcessorFlink")

if __name__ == '__main__':
    main()
