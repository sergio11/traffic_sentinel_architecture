from environment import KAFKA_BOOTSTRAP_SERVERS, KAFKA_INPUT_TOPIC, KAFKA_GROUP_ID

# Function to create the source table in the Flink table environment for processing incoming video frames.
# @Author: Sergio Sánchez Sánchez
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