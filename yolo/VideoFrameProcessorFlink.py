from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment
from pyflink.table.descriptors import Kafka, Json
from vehicle_detection_tracker import VehicleDetectionTracker
import cv2
import numpy as np
import io
import base64

def decode_image(base64_string):
    image_bytes = base64.b64decode(base64_string)
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, flags=cv2.IMREAD_COLOR)
    return image

def process_frame(tracker, base64_frame):
    frame = decode_image(base64_frame)
    processed_frame = tracker.process_frame(frame)
    return processed_frame

def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    t_env = StreamTableEnvironment.create(env)

    # Configurar la conexión a Kafka
    t_env.connect(
        Kafka()
        .version("universal")
        .topic("input_topic")
        .start_from_earliest()
        .property("bootstrap.servers", "localhost:9092")
        .property("group.id", "flink-consumer-group")
    )
    # Configurar el formato de entrada (JSON)
    t_env.with_format(
        Json()
        .json_schema(
            """
            {
                "type": "object",
                "properties": {
                    "frame": {"type": "string"}
                }
            }
            """
        )
        .fail_on_missing_field(True)
    )
    # Registrar la tabla de entrada
    t_env.create_temporary_table("KafkaTable", "frame_data")

    # Crear una instancia de VehicleDetectionTracker
    yolo_cfg = "path_to_yolov4.cfg"
    yolo_weights = "path_to_yolov4.weights"
    yolo_classes = "path_to_coco.names"
    deep_sort_model = "path_to_deep_sort.pb"
    tracker = VehicleDetectionTracker(yolo_cfg, yolo_weights, yolo_classes, deep_sort_model)

    # Definir la consulta para procesar los frames y llamar al método process_frame del VehicleDetectionTracker
    t_env.from_path("KafkaTable")\
        .select("process_frame(frame) AS processed_frame")\
        .execute_insert("ProcessedFrames")

    # Ejecutar el programa
    env.execute("VehicleDetectionProgram")

if __name__ == '__main__':
    main()
