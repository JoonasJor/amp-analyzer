import numpy as np
import matplotlib.colors as mcolors

class PlotDataHandler():
    dataspaces = {}
    '''
    dataspaces structure:
    {
        0: { 
            "name": "dataspace0", 
            "notes": "lorem ipsum",
            "datasets": {
                0: {
                    "name": "dataset0",
                    "times": [0,1,2],
                    "currents": [-0.1,-0.2,-0.3],
                    "concentration": 5.0,
                    "notes": "lorem ipsum",
                    "hidden": False,
                    "line_color": colors[0]
                },
                1: {
                    ...
                }
            }
        },
        1: {
            ...
        }
    }
    '''
    selected_space_id = 0 # Datasets within this space are drawn on the data plot
    active_spaces_ids = [0] # Results within these spaces are drawn on the results plot

    color_index = 0
    colors = []

    time_range = [0,0]

    def __init__(self):
        self.create_color_table()

    def create_color_table(self):
        tableau_colors = mcolors.TABLEAU_COLORS
        css4_colors = mcolors.CSS4_COLORS
        self.colors = list(tableau_colors.values()) + list(css4_colors.values())
        
    def get_smallest_times_dataset(self):
        active_datasets = self.get_datasets_in_active_dataspaces()
        if len(active_datasets) == 0:
            return []
        
        smallest_times_set = []
        for dataset in active_datasets:
            for data in dataset.values():
                if data["hidden"]:
                    continue
                times = data["times"]
                if len(smallest_times_set) == 0 or smallest_times_set[-1] > times[-1]:
                    smallest_times_set = times
        return smallest_times_set

    def add_dataset(self, set_id: int, set_name: str, space_name: str, space_notes: str, times: list, currents: list, concentration: float, notes: str, space_id: int = None, hidden = False, color = None):
        if color == None:
            if self.color_index > len(self.colors) - 1:
                self.color_index = 0
            color = self.colors[self.color_index]
        self.color_index += 1

        dataset = {
            "name": set_name,
            "times": times,
            "currents": currents,
            "concentration": float(concentration),
            "notes": notes,
            "hidden": hidden,
            "line_color": color
        }

        if space_id == None:
            space_id = self.selected_space_id
        # Create new dataspace if id doesnt exist
        if space_id not in self.dataspaces:
            self.dataspaces[space_id] = {
                "name": space_name, 
                "notes": space_notes,
                "datasets": {}
            } 

        datasets = self.get_datasets()
        if set_id in datasets:
            print(f"add_dataset: Dataset with id '{set_id}' already exists. Dataset overwritten")

        # Add dataset to dataspace
        datasets[set_id] = dataset

    def update_dataset(self, set_id, name, concentration, notes):
        datasets = self.get_datasets()
        if set_id in datasets:
            # Update concentration and notes for the specified dataset
            datasets[set_id]['name'] = name
            datasets[set_id]['concentration'] = float(concentration)
            datasets[set_id]['notes'] = notes
            print(datasets[set_id]["name"])
        else:
            print(f"update_dataset: Dataset with id '{set_id}' does not exist.")

    def get_datasets(self, space_id: int = None):
        # If no id provided, get datasets in currently selected space
        if space_id == None:
            space_id = self.selected_space_id

        if space_id in self.dataspaces:
            datasets: dict = self.dataspaces[space_id]["datasets"]
            return datasets   
        else:
            return None
    
    def get_datasets_in_active_dataspaces(self):      
        active_datasets = [self.dataspaces[active_id]["datasets"] for active_id in self.active_spaces_ids if active_id in self.dataspaces]
        return active_datasets

    def delete_dataset(self, set_id):
        pass

    def delete_dataspace(self, space_id = None):
        # If no id provided, delete currently selected space
        if space_id == None:
            space_id = self.selected_space_id
        if not space_id in self.dataspaces:
            return
            
        self.dataspaces.pop(space_id)

    def rename_dataspace(self, space_id, name):
        if space_id in self.dataspaces:
            self.dataspaces[space_id]["name"] = name

    def get_dataspace_names(self):
        names = [self.dataspaces[space_id]["name"] for space_id in self.active_spaces_ids if space_id in self.dataspaces]
        return names

    def calculate_trendline(self, x, y):
        slope, intercept = np.polyfit(x, y, 1)
        r_squared = np.corrcoef(x, y)[0, 1]**2
        trendline = slope * np.array(x) + intercept
        return slope, intercept, r_squared, trendline

    def calculate_results(self, datasets: dict):
        concentration_data = {}
        for data in datasets.values():
            if data["hidden"]:
                continue
            
            times = np.array(data["times"])
            currents = np.array(data["currents"])
            concentration = data["concentration"]

            # Find indices where times fall within the specified range
            indices = np.where((times >= self.time_range[0]) & (times <= self.time_range[1]))[0]

            # Calculate the average current for the specified range
            avg_current = np.mean(currents[indices])

            if concentration in concentration_data:
                concentration_data[concentration].append(avg_current)
            else:
                concentration_data[concentration] = [avg_current]
        
        # Calculate average of average currents for each concentration
        for concentration, currents_list in concentration_data.items():
            concentration_data[concentration] = (np.mean(currents_list), np.std(currents_list))
        sorted_concentration_data = sorted(concentration_data.items())
        return sorted_concentration_data
