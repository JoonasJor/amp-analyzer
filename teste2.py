import time
import os
import pandas as pd
import matplotlib.pyplot as plt
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Function to handle new CSV files
def on_created(event):
    filepath = event.src_path
    if filepath.endswith('.csv'):
        print(f"New CSV file detected: {filepath}")
        plot_from_csv(filepath)

# Function to read CSV file and plot data
def plot_from_csv(csv_file):
    # Read the CSV file into a DataFrame
    df = pd.read_csv(csv_file, encoding="utf-16", header=5)

    # Plot time vs. current for each channel
    for i in range(8):
        if i == 0:
            current_column = "µA"
        else:
            current_column = f"µA.{i}"
        plt.plot(df["s"], df[current_column], label=f"Channel {i}")

    # Add labels and legend
    plt.xlabel("Time")
    plt.ylabel("Current (µA)")
    plt.title("Current vs. Time for Each Channel")
    plt.legend()

    axes = plt.gca()
    axes.xaxis.set_major_locator(plt.MaxNLocator(10))
    axes.yaxis.set_major_locator(plt.MaxNLocator(10))

    # Show plot
    plt.show()

# Function to start monitoring the folder
def start_folder_monitoring(folder):
    event_handler = FileSystemEventHandler()
    event_handler.on_created = on_created

    observer = Observer()
    observer.schedule(event_handler, folder, recursive=False)
    observer.start()

    print(f"Monitoring folder: {folder}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()

# Define the folder to monitor
folder_to_monitor = "D:\\OneDrive - Oulun ammattikorkeakoulu\\Kouluhommat\\PrinLab\\elektrokemiallinen mittaus\\pstrace_helper\\watchdog"

# Start monitoring the folder
start_folder_monitoring(folder_to_monitor)
