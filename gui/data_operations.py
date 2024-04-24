import os
import pandas as pd
import json
import pickle

def handle_csv_data(self, filenames):
    # Doesnt work anymore. Fix or delete later

    data_frame = pd.read_csv(filenames[0], encoding="utf-16", header=5)
    data_frame = data_frame.dropna()
    times = data_frame['s'].astype(float).tolist()

    current_columns = [col for col in data_frame.columns if col.startswith('µA')]

    for currents_column in current_columns:     
        id = self.add_dataset_widget()
        name, concentration, notes = self.get_widgets_text(id)
        currents = data_frame[currents_column].astype(float).tolist()
        self.canvas.add_dataset(id, name, times, currents, concentration, notes)
            
def extract_pssession_pst_data_from_file(filepath):
    if os.path.splitext(filepath)[1] == ".pssession":
        with open(filepath, encoding="utf-16-le") as f:
            data = f.read()
            data = data.replace("\ufeff", "")
            json_data = json.loads(data)
        times = parse_pssession_data_by_type(json_data, "PalmSens.Data.DataArrayTime")
        currents = parse_pssession_data_by_type(json_data, "PalmSens.Data.DataArrayCurrents")
    elif os.path.splitext(filepath)[1] == ".pst":
        with open(filepath, encoding="utf-8") as f:
            data = f.read()
            times, currents = parse_pst_data(data)

    # Attempt extracting directory + channel name from file name             
    try:         
        dir_name = os.path.basename(os.path.dirname(filepath))
        filename = os.path.splitext(os.path.basename(filepath))[0]
        channel = filename.split("-")[0]
        if len(channel) > 1:
            set_name = f"{dir_name} {channel}"
        else:
            set_name = filename
    except Exception as e:
        print(e)

    return times, currents, set_name

def parse_pst_data(data: str):
    times = []
    currents = []

    for line in data.split("\n"):
        if line.strip():
            values = line.split(sep=" ")
            # Ignore lines that dont start with numerical values
            try: 
                float(values[0])
            except ValueError:
                continue

            times.append(float(values[0]))
            currents.append(float(values[1]))
    return times, currents

def parse_pssession_data_by_type(data, target_type):
    # The json is capitalized in newer pssession files
    for key in data.keys():
        if key == "Measurements":
            key_measurements = "Measurements"
            key_dataset = "DataSet"
            key_values = "Values"
            key_type = "Type"
            key_datavalues = "DataValues"
            key_value = "V"
            break
        elif key == "measurements":
            key_measurements = "measurements"
            key_dataset = "dataset"
            key_values = "values"
            key_type = "type"
            key_datavalues = "datavalues"
            key_value = "v"
            break
    
    # Parse data into list
    datavalues = None
    for measurement in data[key_measurements]:
        for value in measurement[key_dataset][key_values]:
            if value[key_type] == target_type:
                datavalues = value[key_datavalues] 
    if datavalues is None:
        return
    
    values = [item[key_value] for item in datavalues]
    return values

def save_program_state_to_file(data: dict, filepath):
    try:
        with open(filepath, "wb") as file:
            pickle.dump(data, file)
        print("File saved at:", filepath)
    except Exception as e:
        print(f"save_program_state_to_file: {e}")

def load_program_state_from_file(filepath):
    try:
        with open(filepath, "rb") as file:
            data = pickle.load(file)
            return data
    except Exception as e:    
        print(f"load_program_state_from_file: {e}")
        return
