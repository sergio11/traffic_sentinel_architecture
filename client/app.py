from io import BytesIO
import os
import tkinter as tk
from PIL import Image, ImageTk
import base64

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
        # Check credentials (dummy example)
        if entry_username.get() == "admin" and entry_password.get() == "password":
            # Destroy login window and open main payload window
            root.destroy()
            display_home_screen()
        else:
            label_error.config(text="Invalid credentials", fg="red")

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

    # Display payload information in a column on the right side
    create_info_label("MAC Address:", example_payload_with_image['mac_address'])
    create_info_label("Camera ID:", example_payload_with_image['camera_id'])
    create_info_label("Frame Timestamp:", example_payload_with_image['frame_timestamp'])

    # Display the base64 image if exists in the payload
    if 'annotated_frame_base64' in example_payload_with_image:
        image_base64 = example_payload_with_image['annotated_frame_base64']
        image = base64.b64decode(image_base64)
        img = Image.open(BytesIO(image))
        img.thumbnail((600, 400)) 
        photo = ImageTk.PhotoImage(img)
        label_image = tk.Label(root, image=photo)
        label_image.image = photo
        label_image.pack()

    root.mainloop()

example_payload_with_image = {
    "mac_address": "02:42:ac:11:00:02",
    "camera_id": "654f6baff3d3ad4f84c41f9e",
    "frame_timestamp": 1699994767
}

display_login_screen()
