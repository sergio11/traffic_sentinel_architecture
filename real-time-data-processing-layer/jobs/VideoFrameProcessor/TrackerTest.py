import os
from collections import defaultdict
import cv2
from VehicleDetectionTracker import VehicleTracker
import numpy as np


# Open the video file
video_path = "https://49-d2.divas.cloud/CHAN-8293/CHAN-8293_1.stream/playlist.m3u8?83.52.13.30&vdswztokenhash=cy0V54p4eY_4209Ljv9UVJqWIa_dIQo24HrIkL8A3qg="
cap = cv2.VideoCapture(video_path)

# Store the track history
track_history = defaultdict(lambda: [])


frame_counter = 0

# Frame rate and time window for speed calculation
frame_rate = 30  # Frames per second (fps)
time_window = 1.0  # Time window for averaging speed (seconds)

# Vehicle speed thresholds for filtering anomalies
speed_threshold_min_kmph = 20.0  # Límite mínimo de velocidad (en km/h)
speed_threshold_max_kmph = 120.0  # Límite máximo de velocidad (en km/h)

tracker = VehicleTracker()

# Loop through the video frames
while cap.isOpened():
    # Read a frame from the video
    success, frame = cap.read()
    if success:
        
        results = tracker.process_frame(frame)
        print(results)

        # Break the loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    else:
        # Break the loop if the end of the video is reached
        break

# Release the video capture object
cap.release()

print(f"Processed {frame_counter} frames.")
