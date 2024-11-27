import tkinter as tk
from tkinter import messagebox, ttk
from threading import Thread
import cv2
import subprocess
import time
import os
import datetime
from urllib.parse import urlparse
from minio import Minio

# MinIO initialization
minio_client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

bucket_name = "video-storagewebcam"
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)

# Camera state management
cameras = {}

# Directory settings
base_directory = "D:/videos_minio/"
os.makedirs(base_directory, exist_ok=True)

# Function to process a camera
def process_camera(camera_id, camera_index):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Camera {camera_id} could not be opened. Skipping.")
        return

    segment_duration = 60  # 60 seconds
    try:
        current_folder = None
        while cameras[camera_id]["enabled"]:
            current_date = datetime.datetime.now().strftime("%Y%m%d")
            if current_folder != current_date:
                current_folder = current_date
                output_directory = os.path.join(base_directory, current_folder)
                os.makedirs(output_directory, exist_ok=True)

            current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"{output_directory}/{camera_id}_{current_time}.mp4"

            ffmpeg_command = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-i", camera_index,
                "-t", str(segment_duration),
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
                output_file,
            ]

            ffmpeg_process = subprocess.Popen(ffmpeg_command)
            ffmpeg_process.wait()

            if os.path.exists(output_file):
                object_name = f"{camera_id}/{current_folder}/{current_time}.mp4"
                minio_client.fput_object(bucket_name, object_name, output_file)
                print(f"Uploaded {object_name} to MinIO.")
                os.remove(output_file)
                print(f"Deleted local file: {output_file}")
            else:
                print(f"File {output_file} not found, skipping upload.")

    except Exception as e:
        print(f"Error processing camera {camera_id}: {e}")
    finally:
        cap.release()
        print(f"Camera {camera_id} stopped.")

# GUI functions
def add_camera():
    # Create a new window for camera input
    camera_window = tk.Toplevel(root)
    camera_window.title("Add Camera")
    camera_window.geometry("300x200")
    
    tk.Label(camera_window, text="Camera IP:").pack(pady=5)
    ip_entry = ttk.Entry(camera_window)
    ip_entry.pack(pady=5)

    tk.Label(camera_window, text="Username:").pack(pady=5)
    username_entry = ttk.Entry(camera_window)
    username_entry.pack(pady=5)

    tk.Label(camera_window, text="Password:").pack(pady=5)
    password_entry = ttk.Entry(camera_window, show="*")
    password_entry.pack(pady=5)

    def save_camera():
        # Retrieve values from entries
        ip = ip_entry.get().strip()
        username = username_entry.get().strip()
        password = password_entry.get().strip()

        if not ip or not username or not password:
            messagebox.showerror("Input Error", "All fields are required.")
            return

        # Construct RTSP URL
        rtsp_url = f"rtsp://{username}:{password}@{ip}:554/live"

        # Generate unique camera ID
        camera_id = ip.replace(".", "_")
        cameras[camera_id] = {"index": rtsp_url, "enabled": True}

        # Update camera list
        update_camera_list()
        camera_window.destroy()
        print(f"Camera {camera_id} added successfully.")

    # Add Save and Cancel buttons
    tk.Button(camera_window, text="Save", command=save_camera).pack(side="left", padx=20, pady=10)
    tk.Button(camera_window, text="Cancel", command=camera_window.destroy).pack(side="right", padx=20, pady=10)

def remove_camera():
    selected = camera_list.selection()
    if not selected:
        messagebox.showwarning("Remove Camera", "No camera selected.")
        return
    for item in selected:
        camera_id = camera_list.item(item, "text")
        cameras.pop(camera_id, None)
        camera_list.delete(item)

def toggle_camera_state():
    selected = camera_list.selection()
    if not selected:
        messagebox.showwarning("Toggle State", "No camera selected.")
        return
    for item in selected:
        camera_id = camera_list.item(item, "text")
        cameras[camera_id]["enabled"] = not cameras[camera_id]["enabled"]
        update_camera_list()

def update_camera_list():
    camera_list.delete(*camera_list.get_children())
    for camera_id, data in cameras.items():
        status = "Enabled" if data["enabled"] else "Disabled"
        camera_list.insert("", "end", text=camera_id, values=(data["index"], status))

def start_processing():
    for camera_id, data in cameras.items():
        if data["enabled"]:
            Thread(target=process_camera, args=(camera_id, data["index"]), daemon=True).start()

# Tkinter UI
root = tk.Tk()
root.title("Dynamic Camera Manager")

frame = tk.Frame(root)
frame.pack(padx=10, pady=10)

camera_list = ttk.Treeview(frame, columns=("RTSP URL", "Status"), show="headings")
camera_list.heading("RTSP URL", text="RTSP URL")
camera_list.heading("Status", text="Status")
camera_list.pack(side="left", fill="both", expand=True)

scrollbar = ttk.Scrollbar(frame, orient="vertical", command=camera_list.yview)
camera_list.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")

button_frame = tk.Frame(root)
button_frame.pack(padx=10, pady=10)

add_button = tk.Button(button_frame, text="Add Camera", command=add_camera)
add_button.grid(row=0, column=0, padx=5, pady=5)

remove_button = tk.Button(button_frame, text="Remove Camera", command=remove_camera)
remove_button.grid(row=0, column=1, padx=5, pady=5)

toggle_button = tk.Button(button_frame, text="Enable/Disable", command=toggle_camera_state)
toggle_button.grid(row=0, column=2, padx=5, pady=5)

start_button = tk.Button(root, text="Start Processing", command=start_processing)
start_button.pack(pady=10)

update_camera_list()
root.mainloop()
