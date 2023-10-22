from pyflink.table import StreamTableEnvironment, EnvironmentSettings
from pyflink.datastream import (
    CheckpointingMode,
    StreamExecutionEnvironment,
    TimeCharacteristic,
)

# Function to set up the Flink execution environment and create a StreamTableEnvironment.
# @Author: Sergio Sánchez Sánchez
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