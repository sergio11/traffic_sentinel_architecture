from environment import KAFKA_BOOTSTRAP_SERVERS, KAFKA_OUTPUT_TOPIC

# Function to create the sink table in the Flink table environment for processed video frames.
# @Author: Sergio Sánchez Sánchez
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
            camera_id STRING,
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