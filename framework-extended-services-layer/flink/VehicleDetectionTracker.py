import cv2
import numpy as np
import pytesseract
from imutils.video import FPS
from deep_sort import DeepSort
from deep_sort.detection import Detection
from deep_sort.tracker import Tracker
from deep_sort import generate_detections as gdet
import redis


class VehicleDetectionTracker:
    def __init__(self, yolo_cfg, yolo_weights, yolo_classes, deep_sort_model, redis_host, redis_port, max_cosine_distance=0.3, nn_budget=None):
        self.net, self.classes, self.output_layers = self.load_yolo(yolo_cfg, yolo_weights, yolo_classes)
        
        self.encoder = gdet.create_box_encoder(deep_sort_model, batch_size=1)
        self.metric = "cosine"
        self.tracker = Tracker(self.metric, max_cosine_distance, nn_budget)
        self.redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0)


    def load_yolo(self, yolo_cfg, yolo_weights, yolo_classes):
        net = cv2.dnn.readNet(yolo_weights, yolo_cfg)
        classes = []
        with open(yolo_classes, "r") as f:
            classes = f.read().strip().split("\n")
        layer_names = net.getLayerNames()
        output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
        return net, classes, output_layers
    
    def detect_objects(self, frame):
        height, width, channels = frame.shape
        blob = cv2.dnn.blobFromImage(frame, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
        self.net.setInput(blob)
        outs = self.net.forward(self.output_layers)

        class_ids = []
        confidences = []
        boxes = []

        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > 0.5:
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)

                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)

                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)

        indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

        detected_objects = []
        for i in range(len(boxes)):
            if i in indexes:
                label = str(self.classes[class_ids[i]])
                confidence = confidences[i]
                box = boxes[i]
                detected_objects.append(Detection(bbox=box, confidence=confidence, class_name=label))

        return detected_objects
    
    def calculate_speed(self, x, y):
        current_time = time.time()
        if hasattr(self, 'previous_time'):
            time_elapsed = current_time - self.previous_time
            displacement = np.sqrt((x - self.previous_x)**2 + (y - self.previous_y)**2)
            speed = displacement / time_elapsed
        else:
            speed = 0.0
        
        self.previous_time = current_time
        self.previous_x = x
        self.previous_y = y
        
        return speed

    def determine_color(self, frame, x, y, w, h):
        vehicle_region = frame[y:y+h, x:x+w]
        hsv_frame = cv2.cvtColor(vehicle_region, cv2.COLOR_BGR2HSV)

        # Definir rangos de colores en HSV
        lower_red = np.array([0, 100, 100])
        upper_red = np.array([10, 255, 255])
        lower_yellow = np.array([20, 100, 100])
        upper_yellow = np.array([40, 255, 255])
        lower_blue = np.array([100, 100, 100])
        upper_blue = np.array([140, 255, 255])

        # Máscaras para segmentar colores
        mask_red = cv2.inRange(hsv_frame, lower_red, upper_red)
        mask_yellow = cv2.inRange(hsv_frame, lower_yellow, upper_yellow)
        mask_blue = cv2.inRange(hsv_frame, lower_blue, upper_blue)

        # Contar píxeles en cada máscara
        red_pixels = cv2.countNonZero(mask_red)
        yellow_pixels = cv2.countNonZero(mask_yellow)
        blue_pixels = cv2.countNonZero(mask_blue)

        # Determinar el color dominante en función de los píxeles
        if red_pixels > yellow_pixels and red_pixels > blue_pixels:
            return "Red"
        elif yellow_pixels > red_pixels and yellow_pixels > blue_pixels:
            return "Yellow"
        elif blue_pixels > red_pixels and blue_pixels > yellow_pixels:
            return "Blue"
        else:
            return "Unknown"

    def determine_size(self, area):
        if area < 5000:
            return "Small"
        elif area < 15000:
            return "Medium"
        else:
            return "Large"

    def determine_vehicle_type(self, area):
        if area < 10000:
            return "car"
        elif area < 25000:
            return "truck"
        elif area < 40000:
            return "bus"
        else:
            return "unknown"

    def detect_license_plate(self, frame, x, y, w, h):
        vehicle_region = frame[y:y+h, x:x+w]
        gray_vehicle = cv2.cvtColor(vehicle_region, cv2.COLOR_BGR2GRAY)

        _, binary_plate = cv2.threshold(gray_vehicle, 150, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary_plate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        license_plate = ""
        for contour in contours:
            x_plate, y_plate, w_plate, h_plate = cv2.boundingRect(contour)
            if w_plate > 50 and h_plate > 20:
                plate_region = binary_plate[y_plate:y_plate+h_plate, x_plate:x_plate+w_plate]
                text = pytesseract.image_to_string(plate_region, config='--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                license_plate += text

        return license_plate

    def process_frame(self, frame, node_id):
        detected_objects = self.detect_objects(frame)

        boxes = np.array([d.tlwh for d in detected_objects])
        scores = np.array([d.confidence for d in detected_objects])
        indices = self.tracker.update(boxes, scores, frame)

        result_data = []

        for i in indices:
            box = boxes[i]
            x, y, w, h = map(int, box)
            label = detected_objects[i].class_name
            confidence = detected_objects[i].confidence
            vehicle_id = self.tracker.tracks[i].track_id
            vehicle_speed = self.calculate_speed(x, y)
            vehicle_color = self.determine_color(frame, x, y, w, h)
            vehicle_size = self.determine_size(w * h)
            license_plate = self.detect_license_plate(frame, x, y, w, h)
            vehicle_type = self.determine_vehicle_type(w * h)

            result_data.append({
                "id": vehicle_id,
                "label": label,
                "confidence": confidence,
                "speed": vehicle_speed,
                "color": vehicle_color,
                "size": vehicle_size,
                "license_plate": license_plate,
                "vehicle_type": vehicle_type
            })

            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, f"{label} {confidence:.2f}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(frame, f"Speed: {vehicle_speed:.2f} px/s", (x, y - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(frame, f"Color: {vehicle_color}", (x, y - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(frame, f"Size: {vehicle_size}", (x, y - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(frame, f"Plate: {license_plate}", (x, y - 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            if not self.redis_client.sismember(f"vehicle_history:{node_id}", vehicle_id):
                self.redis_client.sadd(f"vehicle_history:{node_id}", vehicle_id)
                self.redis_client.hincrby(f"vehicle_counters:{node_id}", "total_vehicles", 1)
                self.redis_client.hincrby(f"vehicle_counters:{node_id}", f"{vehicle_type}_vehicles", 1)
       
        response_json = {
            "frame_data": frame,
            "tracked_objects": result_data
        }

        return response_json

if __name__ == "__main__":
    yolo_cfg = "path_to_yolov4.cfg"
    yolo_weights = "path_to_yolov4.weights"
    yolo_classes = "path_to_coco.names"
    deep_sort_model = "path_to_deep_sort.pb"
    
    cap = cv2.VideoCapture("path_to_input_video.mp4")
    tracker = VehicleDetectionTracker(yolo_cfg, yolo_weights, yolo_classes, deep_sort_model)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        processed_frame = tracker.process_frame(frame)

        cv2.imshow("Processed Frame", processed_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
