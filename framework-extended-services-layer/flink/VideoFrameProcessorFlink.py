from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table.descriptors import Schema, Kafka, Json
from pyflink.table import StreamTableEnvironment, DataTypes
from pyflink.table.window import Tumble
from vehicle_detection_tracker import VehicleDetectionTracker
import cv2
import numpy as np
import io
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

    env = StreamExecutionEnvironment.get_execution_environment()
    t_env = StreamTableEnvironment.create(env)

    schema = Schema()
    schema.field("mac_address", DataTypes.STRING())
    schema.field("timestamp", DataTypes.BIGINT())
    schema.field("frame_data", DataTypes.STRING())

    t_env.connect(
        Kafka()
        .version("universal")
        .topic(kafka_config["topic"])
        .start_from_earliest()
        .property("bootstrap.servers", kafka_config["bootstrap.servers"])
        .property("group.id", kafka_config["group.id"])
        .json_schema(Json().schema(schema))
    )
    # Registrar la tabla de entrada
    t_env.create_temporary_table("KafkaTable", "frame_data")

    t_env.from_path("KafkaTable") \
    .select("CAST(mac_address AS STRING) AS mac_address, CAST(timestamp AS BIGINT) AS timestamp, CAST(frame_data AS STRING) AS frame_data") \
    .window(Tumble.over("5.seconds").on("timestamp").alias("w")) \
    .group_by("mac_address, w") \
    .select("process_batch(mac_address, timestamp, COLLECT_LIST(frame_data)) AS processed_payload") \
    .to_append_stream(t_env.sink_to_kafka(
        "frame_processed",
        {"bootstrap.servers": "localhost:9092"},
        value_delimiter="\n"
    ))

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

if __name__ == '__main__':
    main()
