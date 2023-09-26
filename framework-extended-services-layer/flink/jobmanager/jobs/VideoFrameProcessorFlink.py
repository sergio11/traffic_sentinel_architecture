from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors import FlinkKafkaConsumer, FlinkKafkaProducer
from pyflink.table import StreamTableEnvironment, DataTypes, EnvironmentSettings
from pyflink.table.window import Tumble
from vehicle_detection_tracker import VehicleDetectionTracker
import cv2
import numpy as np
import base64
import json

kafka_config = {
    "topic": "input_topic",
    "bootstrap.servers": "localhost:9092",
    "group.id": "flink-consumer-group"
}

tracker = None

def main():
    global tracker
    # Crear una instancia de VehicleDetectionTracker
    yolo_cfg = "path_to_yolov4.cfg"
    yolo_weights = "path_to_yolov4.weights"
    yolo_classes = "path_to_coco.names"
    deep_sort_model = "path_to_deep_sort.pb"
    tracker = VehicleDetectionTracker(yolo_cfg, yolo_weights, yolo_classes, deep_sort_model)

    env_settings = EnvironmentSettings.new_instance().use_blink_planner().build()
    env = StreamExecutionEnvironment.get_execution_environment()
    t_env = StreamTableEnvironment.create(env, environment_settings=env_settings)

    schema = DataTypes.ROW([
        DataTypes.FIELD("mac_address", DataTypes.STRING()),
        DataTypes.FIELD("timestamp", DataTypes.BIGINT()),
        DataTypes.FIELD("frame_data", DataTypes.STRING())
    ])

    properties = {
        "bootstrap.servers": kafka_config["bootstrap.servers"],
        "group.id": kafka_config["group.id"],
        "format": "json"
    }

    kafka_source = FlinkKafkaConsumer(
        kafka_config["topic"],
        schema,
        properties=properties
    ).start_from_earliest()

    kafka_sink = FlinkKafkaProducer(
        "frame_processed",
        schema,
        producer_config={
            "bootstrap.servers": "localhost:9092"
        },
        serialization_schema=JsonRowSerializationSchema()
    )

    t_env.create_temporary_table("KafkaTable", kafka_source)

    t_env.from_path("KafkaTable") \
    .select("CAST(mac_address AS STRING) AS mac_address, CAST(timestamp AS BIGINT) AS timestamp, CAST(frame_data AS STRING) AS frame_data") \
    .window(Tumble.over("5.seconds").on("timestamp").alias("w")) \
    .group_by("mac_address, w") \
    .select("process_batch(mac_address, timestamp, COLLECT_LIST(frame_data)) AS processed_payload") \
    .to_append_stream(kafka_sink)

    # Ejecutar el programa
    env.execute("VehicleDetectionProgram")

# Función de utilidad para decodificar una imagen en base64
def _decode_image(base64_string):
    image_bytes = base64.b64decode(base64_string)
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, flags=cv2.IMREAD_COLOR)
    return image

# Función de utilidad para procesar un frame
def _process_frame(mac_address, timestamp, frame_data):
    frame = _decode_image(frame_data)
    processed_frame = tracker.process_frame(frame)
    
    processed_payload = {
        'mac_address': mac_address,
        'timestamp': timestamp,
        'processed_frame': processed_frame.tolist()  # Convert processed_frame to list for JSON serialization
    }
    return json.dumps(processed_payload)

# Función de procesamiento en lote
def process_batch(mac_address, window_start, frame_data_list):
    global tracker
    # Procesa cada frame en el lote utilizando el tracker.
    processed_frames = []
    for frame_data in frame_data_list:
        frame_data = json.loads(frame_data)
        mac_address = frame_data['mac_address']
        timestamp = frame_data['timestamp']
        base64_frame = frame_data['frame_data']
        
        processed_frame = _process_frame(mac_address, timestamp, base64_frame)
        processed_frames.append(processed_frame)

    return processed_frames

class JsonRowSerializationSchema(SerializationSchema):

    def __init__(self):
        pass

    def serialize(self, element):
        return json.dumps(element).encode('utf-8')

if __name__ == '__main__':
    main()