import base64
import io
import json
import logging
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import Toplevel, ttk
from tkinter.ttk import Treeview
from PIL import Image, ImageTk
import requests
import socketio
import datetime
from tkinter import messagebox

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

AUTHENTICATE_ENDPOINT = os.environ.get("AUTHENTICATE_ENDPOINT", "http://localhost:5003/users/authenticate")
STREAM_SERVICE_ENDPOINT = os.environ.get("STREAM_SERVICE_ENDPOINT", "http://localhost:5004")
STREAM_SERVICE_NAMESPACE = os.environ.get("STREAM_SERVICE_NAMESPACE", "/traffic_sentinel_stream")

def _bind_event_data(widget, sequence, func, add = None):
    def _substitute(*args):
        e = lambda: None #simplest object with __dict__
        e.data = eval(args[0])
        e.widget = widget
        return (e,)
    funcid = widget._register(func, _substitute, needcleanup=1)
    cmd = '{0}if {{"[{1} %d]" == "break"}} break\n'.format('+' if add else '', funcid)
    widget.tk.call('bind', widget._w, sequence, cmd)


def display_login_screen():
    root = tk.Tk()
    root.title("Traffic Sentinel - Login")
    root.geometry("800x600")

    # Load background image with transparency
    background_path = os.path.join("resources", "background.jpg")
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
        image_label = tk.Label(content_frame, image=photo, bg="white")
        image_label.image = photo
        image_label.pack(pady=(0, 10))

    def login():
        username = entry_username.get()
        password = entry_password.get()
        payload = {"username": username, "password": password}

        def authenticate_user():
            response = requests.post(AUTHENTICATE_ENDPOINT, json=payload)
            if response.status_code == 200:
                logger.info("User authenticated successfully.")
                session_token = response.json()["session_token"]
                root.event_generate("<<SuccessfulAuth>>", when="tail", data={"session_token": session_token})
            else:
                logger.error("Invalid credentials provided.")
                root.event_generate("<<UnSuccessfulAuth>>", when="tail")
            logger.info("Authentication initiated.")

        auth_thread = threading.Thread(target=authenticate_user)
        auth_thread.start()

    label_username = tk.Label(content_frame, bg="white", text="Username", font=("Arial", 12, "bold"))
    label_username.pack(pady=(20, 0))
    entry_username = tk.Entry(content_frame, font=("Arial", 12))
    entry_username.pack()
    label_password = tk.Label(content_frame, bg="white", text="Password", font=("Arial", 12, "bold"))
    label_password.pack(pady=(20, 0))
    entry_password = tk.Entry(content_frame, show="*", font=("Arial", 12))
    entry_password.pack()
    button_login = tk.Button(content_frame, text="Login", command=login, font=("Arial", 10), bg="black", fg="white", width=20)
    button_login.pack(pady=(20, 0))
    label_error = tk.Label(content_frame, bg="white", text="", fg="red", font=("Arial", 10))
    label_error.pack(pady=(20, 0))

    def on_successful_auth(event):
        root.destroy()
        logger.info(f"Authenticate successfully with session token: #{event.data['session_token']}")
        display_home_screen(event.data['session_token'])

    def on_unsuccessful_auth(event):
        label_error.config(text="Invalid credentials", fg="red")

    _bind_event_data (root, '<<SuccessfulAuth>>', on_successful_auth)
    root.bind("<<UnSuccessfulAuth>>", on_unsuccessful_auth)

    root.mainloop()

def display_home_screen(session_token):

    def load_cameras():
        headers = {
            "Authentication": session_token
        }
        response = requests.get("http://localhost:5002/cameras/list", headers=headers)
        if response.status_code == 200:
            cameras_data = response.json()["data"]["cameras"]
            root.event_generate("<<CamerasLoaded>>", when="tail", data=cameras_data)


    def on_cameras_loaded(event):
        cameras_data = event.data
        camera_table_frame = tk.Frame(root)
        camera_table_frame.grid(row=1, column=0, sticky="nsew")

        def on_table_click(event):
            item = tree.focus()
            if item:
                camera_id = tree.item(item, "values")[0] 
                camera_name = tree.item(item, "values")[2]
                root.destroy()
                display_monitoring_screen(session_token, camera_id, camera_name)


        tree = ttk.Treeview(camera_table_frame, columns=("Camera ID", "Address", "Camera Name", "Max Speed Limit", "Region", "Vehicles Detected"))
        scrollbar = ttk.Scrollbar(camera_table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)

        tree.heading("#0", text="Index")
        tree.heading("Camera ID", text="Camera ID")
        tree.heading("Address", text="Address")
        tree.heading("Camera Name", text="Camera Name")
        tree.heading("Max Speed Limit", text="Max Speed Limit")
        tree.heading("Region", text="Region")
        tree.heading("Vehicles Detected", text="Vehicles Detected")

        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.grid(row=0, column=0, sticky="nsew")

        for i, camera in enumerate(cameras_data, start=1):
            tree.insert("", "end", text=f"{i}", values=(
                camera["_id"],
                camera["address"],
                camera["camera_name"],
                camera["max_speed_limit"],
                camera["region"],
                camera.get("vehicles_detected", "-"),
                ""
            ))

        tree.bind("<Double-1>", on_table_click)

    root = tk.Tk()
    root.title("Traffic Sentinel - HOME")
    root.geometry("1200x400")

    title_frame = tk.Frame(root, bg="white", height=50)
    title_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

    logo_path = "resources/logo.png"
    try:
        logo_image = Image.open(logo_path)
        logo_image = logo_image.resize((40, 40), Image.LANCZOS)
        logo = ImageTk.PhotoImage(logo_image)
        logo_label = tk.Label(title_frame, image=logo, bg="lightgreen")
        logo_label.image = logo
        logo_label.grid(row=0, column=0, padx=10, pady=5)
    except FileNotFoundError:
        print(f"File {logo_path} not found.")

    app_title_label = tk.Label(title_frame, bg="white", text="Traffic Sentinel - Driving Smarter Roads with IoT Traffic Monitoring", font=("Arial", 16, "bold"))
    app_title_label.grid(row=0, column=1, padx=10, pady=10)

    _bind_event_data (root, '<<CamerasLoaded>>', on_cameras_loaded)
    threading.Thread(target=load_cameras, daemon=True).start()
    root.mainloop()


def display_monitoring_screen(session_token, camera_id, camera_name):

    event_queue = queue.Queue()
    current_socketio = None
    update_gui_job_id = None
    closing_monitoring_in_progress = False
    existing_vehicles = {}

    root = tk.Tk()
    root.title(f"Traffic Sentinel - Monitoring #{camera_name}")
    root.geometry("1200x800")

    # Function to create and format labels for displaying information
    def _create_info_label(frame, label_text, value, row, padx, pady):
        label = tk.Label(frame, text=label_text, font=("Arial", 12, "bold"), fg="blue")
        label.grid(row=row, column=0, sticky="w", padx=padx, pady=pady)
        value_label = tk.Label(frame, text=value, font=("Arial", 12))
        value_label.grid(row=row, column=1, sticky="w", padx=padx, pady=pady)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        return value_label

    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)

    title_frame = tk.Frame(root, bg="white", height=50)
    title_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

    logo_path = "resources/logo.png"
    try:
        logo_image = Image.open(logo_path)
        logo_image = logo_image.resize((40, 40), Image.ANTIALIAS)
        logo = ImageTk.PhotoImage(logo_image)
        logo_label = tk.Label(title_frame, image=logo, bg="lightgreen")
        logo_label.image = logo
        logo_label.grid(row=0, column=0, padx=10, pady=5)
    except FileNotFoundError:
        print(f"File {logo_path} not found")


    app_title_label = tk.Label(title_frame, bg="white", text="Traffic Sentinel - Driving Smarter Roads with IoT Traffic Monitoring", font=("Arial", 16, "bold"))
    app_title_label.grid(row=0, column=1, padx=10, pady=10)

    connected_label = tk.Label(title_frame, font=("Arial", 10), bg="white", text="Not connected", fg="red")
    connected_label.grid(row=0, column=2, padx=10, pady=5)

    left_frame = tk.Frame(root, height=400)
    left_frame.grid(row=1, column=0, sticky="nsew")

    right_frame = tk.Frame(root, height=400)
    right_frame.grid(row=1, column=1, sticky="nsew")


    mac_address_label_value = _create_info_label(right_frame, "MAC Address:", "N/S", 1, 20, 5)
    camera_id_label_value = _create_info_label(right_frame, "Camera ID:", "N/S", 2, 20, 5)
    frame_timestamp_label_value = _create_info_label(right_frame, "Frame Timestamp:", "N/S", 3, 20, 5)
    number_of_vehicles_label_value = _create_info_label(right_frame, "Number of Vehicles Detected:", "N/S", 4, 20, 5)

    empty_label = tk.Label(right_frame, text="", font=("Arial", 12))
    empty_label.grid(row=0, column=0, columnspan=2)
    
    default_image = Image.open("resources/default_no_available.png")
    default_image = default_image.resize((500, 400))
    default_image_tk = ImageTk.PhotoImage(default_image)
    annotated_frame_label = tk.Label(left_frame, image=default_image_tk)
    annotated_frame_label.pack(expand=True, fill='both', padx=20, pady=20)

    root.grid_rowconfigure(0, weight=0)
    root.grid_rowconfigure(1, weight=1)
    root.grid_rowconfigure(2, weight=0)

    vehicle_table_frame = tk.Frame(root, bg="white")
    vehicle_table_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")

    vehicle_table_frame = tk.Frame(root, bg="white")
    vehicle_table_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")

    tree = Treeview(vehicle_table_frame, columns=("Vehicle ID", "Type", "Color", "Model", "Speed", "Direction"))
    scrollbar = tk.Scrollbar(vehicle_table_frame, orient='vertical', command=tree.yview)
    tree.configure(yscroll=scrollbar.set)

    tree.heading("Vehicle ID", text="Vehicle ID")
    tree.heading("Type", text="Type")
    tree.heading("Color", text="Color")
    tree.heading("Model", text="Model")
    tree.heading("Speed", text="Speed")
    tree.heading("Direction", text="Direction")

    scrollbar.pack(side='right', fill='y')
    tree.pack(expand=True, fill='both')

    bottom_frame = tk.Frame(root, bg="white")
    bottom_frame.grid(row=3, column=0, columnspan=2, sticky="ew")

    copyright_label = tk.Label(bottom_frame, bg="white", text="© 2023 Traffic Sentinel. All rights reserved.  |  Created and Developed by: Sergio Sánchez Sánchez", font=("Arial", 10))
    copyright_label.pack(padx=10, pady=5)

    def update_annotated_frame(image_base64):
        if image_base64:
            annotated_frame_bytes = base64.b64decode(image_base64.split(',')[-1])
            annotated_frame_image = Image.open(io.BytesIO(annotated_frame_bytes))
            annotated_frame_image = annotated_frame_image.resize((600, 400))
            annotated_frame_tk = ImageTk.PhotoImage(annotated_frame_image)
            annotated_frame_label.configure(image=annotated_frame_tk)
            annotated_frame_label.image = annotated_frame_tk

    def connect_to_server():
        MAX_RETRIES = 5 
        RETRY_DELAY = 5
        retries = 0
        
        while retries < MAX_RETRIES:
            logger.info(f"Attempting connection... (Attempt {retries + 1}/{MAX_RETRIES})")
            current_socketio = socketio.Client()

            @current_socketio.on('new_frame')
            def handle_new_frame(payload):
                logger.info(f"on new frame received")
                try:
                    event_queue.put_nowait(payload)
                except queue.Full:
                    pass

            @current_socketio.on('connect')
            def on_connect():
                logger.info("Connected to server")
                current_socketio.emit('subscribe_camera', {'session_token': session_token, 'camera_id': camera_id})
                logger.info(f"Subscribed to camera {camera_id}")
                root.event_generate("<<OnConnected>>", when="tail")

            @current_socketio.on('disconnect')
            def on_disconnect():
                logger.info("Disconnected from server")
                root.event_generate("<<OnDisconnected>>", when="tail")

            @current_socketio.on('subscription_success')
            def on_subscribe_success(data):
                logger.info(f"Subscription to camera successfully - {data}")

            @current_socketio.on('unsubscription_success')
            def on_subscribe_success(data):
                logger.info(f"Unsubscription from camera successfully - {data}")

            @current_socketio.on('subscription_error')
            def on_subscribe_error(data):
                logger.info(f"Subscription to camera error" - {data})
                if current_socketio is not None:
                    current_socketio.disconnect()

            try:
                current_socketio.connect(STREAM_SERVICE_ENDPOINT)
                break
            except Exception as e:
                logger.error(f"Error connecting: {e}")
                retries += 1
                if retries >= MAX_RETRIES:
                    logger.error("Maximum retries reached. Cannot connect.")
                    break
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)

        if retries >= MAX_RETRIES:
            root.event_generate("<<StreamingServerUnreachable>>", when="tail")

    def handle_frame_payload(payload):
        logger.info("Handling frame payload")
        mac_address_label_value["text"] = payload.get("mac_address", "N/S")
        camera_id_label_value["text"] = payload.get("camera_id", "N/S")
        timestamp = payload.get("frame_timestamp")
        formatted_timestamp = "N/S"
        if timestamp:
            try:
                datetime_obj = datetime.datetime.fromtimestamp(timestamp)
                formatted_timestamp = datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logger.error(f"Error formatting timestamp: {e}")
        frame_timestamp_label_value["text"] = formatted_timestamp
        processed_frame = payload.get("processed_frame", "{}")
        try:
            processed_frame_payload = eval(processed_frame)
            if not isinstance(processed_frame_payload, dict):
                processed_frame_payload = {}
        except Exception as e:
            logger.error(f"Error evaluating processed_frame JSON: {e}")
            processed_frame_payload = {}

        if 'annotated_frame_base64' in processed_frame_payload:
            annotated_frame_base64 = processed_frame_payload['annotated_frame_base64']
            update_annotated_frame(annotated_frame_base64)

        if 'detected_vehicles' in processed_frame_payload:
            logger.info("detected_vehicles in processed_frame_payload CALLED!")
            detected_vehicles = processed_frame_payload['detected_vehicles']
            for idx, vehicle in enumerate(detected_vehicles):
                vehicle_id = vehicle.get('vehicle_id', 'N/A')
                vehicle_type = vehicle.get('vehicle_type', 'N/A')
                color_info = json.loads(vehicle.get('color_info', '[]'))
                color = color_info[0]['color'] if color_info else 'N/A'
                speed_info = vehicle.get('speed_info', {})
                speed = speed_info.get('kph', 'N/A')
                direction_label = speed_info.get('direction_label', 'N/A')
                model_info = json.loads(vehicle.get('model_info', '[]'))
                make = model_info[0].get('make', 'N/A')
                model = model_info[0].get('model', 'N/A')
                make_model_combined = f"{make} {model}"
                logger.info(f"#idx - #{idx} vehicle_id #{vehicle_id}")
                if vehicle_id in existing_vehicles:
                    item_id = existing_vehicles[vehicle_id]
                    tree.item(item_id, values=(vehicle_id, vehicle_type, color, make_model_combined, speed, direction_label))
                else:
                    item_id = tree.insert("", tk.END, text=str(len(existing_vehicles)), values=(vehicle_id, vehicle_type, color, make_model_combined, speed, direction_label))
                    existing_vehicles[vehicle_id] = item_id

        number_of_vehicles_label_value["text"] = len(existing_vehicles)
        
    def update_gui():
        try:
            payload = event_queue.get(block=False)
            handle_frame_payload(json.loads(payload))
        except queue.Empty:
            pass
        global update_gui_job_id
        update_gui_job_id = root.after(1000, update_gui)

    def stop_update_gui():
        global update_gui_job_id
        if update_gui_job_id:
            root.after_cancel(update_gui_job_id)
            update_gui_job_id = None
        
    def handle_streaming_server_unreachable(event):
        root.destroy()
        display_home_screen(session_token)

    def handle_on_connected(event):
        connected_label['text'] = "Connected"
        connected_label['fg'] = "green"

    def handle_on_disconnected(event):
        connected_label['text'] = "Not connected"
        connected_label['fg'] = "red"
        if connect_thread and connect_thread.is_alive():
            connect_thread.cancel()
            connect_thread.join()
        if closing_monitoring_in_progress:
            root.destroy()
            display_home_screen(session_token)
        else:
            connect_thread = threading.Thread(target=connect_to_server)
            connect_thread.start()

    root.bind("<<StreamingServerUnreachable>>", handle_streaming_server_unreachable)
    root.bind("<<OnDisconnected>>", handle_on_disconnected)
    root.bind("<<OnConnected>>", handle_on_connected)

    def on_closing():
        if messagebox.askokcancel("Close Monitoring", "¿Are you sure to close monitoring?"):
            global closing_monitoring_in_progress
            closing_monitoring_in_progress = True
            stop_update_gui()
            if connect_thread and connect_thread.is_alive():
                connect_thread.cancel()
                connect_thread.join()
            if current_socketio is not None:
                current_socketio.emit('unsubscribe_camera', {'session_token': session_token, 'camera_id': camera_id})

    root.protocol("WM_DELETE_WINDOW", on_closing)

    update_gui()

    connect_thread = threading.Thread(target=connect_to_server)
    connect_thread.start()

    root.mainloop()

display_login_screen()