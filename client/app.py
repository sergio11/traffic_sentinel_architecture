from io import BytesIO
import logging
import os
import threading
import tkinter as tk
from PIL import Image, ImageTk
import base64
import requests
import socketio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

AUTHENTICATE_ENDPOINT = os.environ.get("AUTHENTICATE_ENDPOINT", "http://localhost:5003/users/authenticate")
STREAM_SERVICE_ENDPOINT = os.environ.get("STREAM_SERVICE_ENDPOINT", "http://localhost:5004")
STREAM_SERVICE_NAMESPACE = os.environ.get("STREAM_SERVICE_NAMESPACE", "/traffic_sentinel_stream")

def display_login_screen():
    root = tk.Tk()
    root.title("Traffic Sentinel - Login")
    root.geometry("800x600")

    # Load background image with transparency
    background_path = os.path.join("resources", "background.jpg")  # Use an image with transparency (e.g., PNG)
    if os.path.exists(background_path):
        background_img = Image.open(background_path)
        background_img = background_img.resize((800, 600), Image.LANCZOS)
        background_photo = ImageTk.PhotoImage(background_img)
        background_label = tk.Label(root, image=background_photo)
        background_label.image = background_photo
        background_label.place(x=0, y=0, relwidth=1, relheight=1)

    # Create a frame for the login content
    content_frame = tk.Frame(root)
    content_frame.configure(bg='#f7f7f7')
    content_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # Load and display the logo image
    image_path = os.path.join("resources", "logo.png")
    if os.path.exists(image_path):
        img = Image.open(image_path)
        img = img.resize((300, 200), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        image_label = tk.Label(content_frame, image=photo, bg="white")  # Use a solid background color for the image label
        image_label.image = photo
        image_label.pack(pady=(0, 10))  # Add vertical space above and below

    def login():
        username = entry_username.get()
        password = entry_password.get()
        payload = {"username": username, "password": password}

        def authenticate_user():
            response = requests.post(AUTHENTICATE_ENDPOINT, json=payload)
            if response.status_code == 200:
                logger.info("User authenticated successfully.")
                root.event_generate("<<SuccessfulAuth>>", when="tail")
            else:
                logger.error("Invalid credentials provided.")
                root.event_generate("<<UnSuccessfulAuth>>", when="tail")
            logger.info("Authentication initiated.")

        auth_thread = threading.Thread(target=authenticate_user)
        auth_thread.start()

    label_username = tk.Label(content_frame, text="Username", font=("Arial", 12, "bold"))
    label_username.pack(pady=(20, 0))
    entry_username = tk.Entry(content_frame, font=("Arial", 12))
    entry_username.pack()
    label_password = tk.Label(content_frame, text="Password", font=("Arial", 12, "bold"))
    label_password.pack(pady=(20, 0))
    entry_password = tk.Entry(content_frame, show="*", font=("Arial", 12))
    entry_password.pack()
    button_login = tk.Button(content_frame, text="Login", command=login, font=("Arial", 10), bg="black", fg="white", width=20)
    button_login.pack(pady=(20, 0))
    label_error = tk.Label(content_frame, text="", fg="red", font=("Arial", 10))
    label_error.pack(pady=(20, 0))

    def on_successful_auth(event):
        root.destroy()
        display_home_screen()

    def on_unsuccessful_auth(event):
        label_error.config(text="Invalid credentials", fg="red")

    root.bind("<<SuccessfulAuth>>", on_successful_auth)
    root.bind("<<UnSuccessfulAuth>>", on_unsuccessful_auth)

    root.mainloop()


def display_home_screen():
    root = tk.Tk()
    root.title("Traffic Sentinel - HOME")
    root.geometry("800x600")

    project_title = tk.Label(root, text="Traffic Sentinel - Driving Smarter Roads with IoT Traffic Monitoring",
                             font=("Arial", 16, "bold"))
    project_title.pack(pady=10)
    info_frame = tk.Frame(root)
    info_frame.pack(padx=10, pady=10)

    # Function to create and format labels for displaying information
    def create_info_label(label_text, value):
        label = tk.Label(info_frame, text=label_text, font=("Arial", 12, "bold"), fg="blue")
        label.pack(anchor=tk.E)
        value_label = tk.Label(info_frame, text=value, font=("Arial", 12))
        value_label.pack(anchor=tk.E)

    def connect_to_server():
        sio = socketio.Client()

        @sio.on('new_frame')
        def handle_new_frame(payload):
            logger.info(f"on new frame received")
            root.event_generate("<<FramePayload>>", when="tail", detail=payload)

        @sio.on('connect')
        def on_connect():
            logger.info("Connected to server")
            camera_id = '654f6baff3d3ad4f84c41f9e'
            sio.emit('subscribe_camera', {'camera_id': camera_id})
            logger.info(f"Subscribed to camera {camera_id}")

        sio.connect(STREAM_SERVICE_ENDPOINT, namespaces=[STREAM_SERVICE_NAMESPACE])
        sio.wait()

    connect_thread = threading.Thread(target=connect_to_server)
    connect_thread.start()

    def handle_frame_payload(data):
        create_info_label("MAC Address:", data['mac_address'])
        create_info_label("Camera ID:", data['camera_id'])
        create_info_label("Frame Timestamp:", data['frame_timestamp'])

        if 'annotated_frame_base64' in data:
            image_base64 = data['annotated_frame_base64']
            image = base64.b64decode(image_base64)
            img = Image.open(BytesIO(image))
            img.thumbnail((600, 400))
            photo = ImageTk.PhotoImage(img)
            label_image = tk.Label(root, image=photo)
            label_image.image = photo
            label_image.pack()

    root.bind("<<FramePayload>>", handle_frame_payload)

    root.mainloop()

display_login_screen()