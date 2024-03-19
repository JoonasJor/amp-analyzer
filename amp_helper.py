import json
import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QFileDialog, QCheckBox, QLabel, QFrame
from PyQt6.uic import loadUi
from PyQt6.QtCore import Qt, QFileInfo
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector, SpanSelector
import numpy as np
import pandas as pd
import pyperclip
from io import StringIO

class MyMainWindow(QMainWindow):
    space_widget_id = 0
    set_widget_id = 0
    button_add_dataset = None
    layout_datasets = None
    widgets = {}
    '''
    widgets structure:
    {
        space_id0: { 
            "dataspace_widgets": {
                "checkbox_toggle": checkbox_toggle_space,
                "button_space": button_space
            },
            "dataset_widgets": {
                dataset_id0: {
                    "checkbox_toggle": checkbox_toggle_active,
                    "line_edit_name": line_edit_name,
                    "line_edit_concentration": line_edit_concentration,
                    "line_edit_notes": line_edit_notes,
                    "button_paste": button_paste
                },
                dataset_id1: {
                    "checkbox_toggle": checkbox_toggle_active,
                    "line_edit_name": line_edit_name,
                    "line_edit_concentration": line_edit_concentration,
                    "line_edit_notes": line_edit_notes,
                    "button_paste": button_paste
                }
            }
        },
        space_id1 {
            ...
        }
    }
    '''

    def __init__(self):
        super().__init__()

        loadUi("amp_helper.ui", self)
        # Enable dropping onto the main window
        self.setAcceptDrops(True)

        self.canvas = PlotCanvas(self.plotWidget)
        layout = QVBoxLayout(self.plotWidget)
        layout.addWidget(self.canvas)
        layout.setContentsMargins(2, 2, 2, 2)

        # Menu button signals
        self.actionImport_data_from_CSV.triggered.connect(self.on_import_data_from_csv_clicked)
        self.actionImport_data_from_PSSESSION.triggered.connect(self.on_import_data_from_pssession_clicked)
        self.actionDebug_Info.triggered.connect(self.canvas.toggle_debug_info)
        self.actionLegend.triggered.connect(self.canvas.toggle_legend)
        self.actionEquation.triggered.connect(self.canvas.toggle_equation)

        # Dataspace signals
        self.pushButton_dataspace_add.clicked.connect(lambda: self.add_dataspace_widget())
        self.pushButton_dataspace_remove.clicked.connect(self.on_dataspace_remove_clicked)
        self.pushButton_dataspace_rename.clicked.connect(self.on_dataspace_rename_clicked)

        # Bidirectional connection for plot seconds slider and lineEdit
        #self.horizontalSlider_plot_seconds.valueChanged.connect(lambda value, le=self.lineEdit_plot_seconds: le.setText(str(value)))
        #self.lineEdit_plot_seconds.editingFinished.connect(lambda: self.horizontalSlider_plot_seconds.setValue(int(self.lineEdit_plot_seconds.text())))

        # Matplotlib navigation toolbar
        navigation_toolbar = NavigationToolbar(self.canvas, self)
        self.verticalLayout_toolbox.addWidget(navigation_toolbar)
        #self.verticalLayout_toolbox.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.layout_datasets = QVBoxLayout(self.widget_datasets)
        #self.widget_datasets.setStyleSheet("border: 1px solid grey;")  

        label_spacer = QLabel(self)
        label_spacer.setFixedWidth(40)
        label_name = QLabel(self)
        label_name.setText("Name")
        label_name.setFixedWidth(100)
        label_spacer2 = QLabel(self)
        label_spacer2.setFixedWidth(5)
        label_concentration = QLabel(self)
        label_concentration.setText("Concentration")
        label_name.setFixedWidth(50)
        label_notes = QLabel(self)
        label_notes.setText("Notes")

        hbox = QHBoxLayout()
        hbox.addWidget(label_spacer)
        hbox.addWidget(label_name)
        hbox.addWidget(label_spacer2)
        hbox.addWidget(label_concentration)
        hbox.addWidget(label_notes)

        # Add hbox to parent layout
        self.layout_datasets.addLayout(hbox)

        # Initialize one dataspace
        self.add_dataspace_widget()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            event.ignore()
            return
        
        # Parse folders and individual files from dropped files
        files = [url.toLocalFile() for url in mime_data.urls()]
        folders = [file for file in files if QFileInfo(file).isDir()]
        individual_files = [file for file in files if QFileInfo(file).isFile()]

        # Add individual files and files inside all folders to single list
        filepaths = []
        if folders:
            for folder in folders:
                for root, _, filenames in os.walk(folder):
                    filepaths.extend([os.path.join(root, filename) for filename in filenames if filename.endswith('.pssession')])
        if individual_files:
            filepaths.extend([file for file in individual_files if file.endswith('.pssession')])

        self.handle_pssession_data(sorted(filepaths))
            

    def add_dataspace_widget(self):
        space_id = self.space_widget_id
        self.space_widget_id += 1
        space_name = f"Set {space_id}"

        checkbox_toggle_space = QCheckBox(self)
        checkbox_toggle_space.setChecked(True)
        checkbox_toggle_space.stateChanged.connect(lambda: self.set_active_dataspaces())

        button_space = QPushButton(space_name, self)
        button_space.clicked.connect(lambda: self.switch_dataspace(space_id))
        button_space.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")

        hbox = QHBoxLayout()
        hbox.addWidget(checkbox_toggle_space)
        hbox.addWidget(button_space, stretch=1)

        self.verticalLayout_dataspaces.addLayout(hbox)
        self.verticalLayout_dataspaces.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Store references to the widgets for later access
        self.widgets[space_id] = { 
            "dataspace_widgets": {
                "checkbox_toggle": checkbox_toggle_space,
                "button_space": button_space
            },
            "dataset_widgets": {}
        }

        # Initialize every space with one dataset
        self.switch_dataspace(space_id)
        set_id = self.add_dataset_widget()
        set_name, concentration, notes = self.get_widgets_text(set_id)
        times = np.arange(0, 100.1, 0.1)
        currents = np.linspace(-15, -5, len(times))
        self.set_active_dataspaces()
        self.canvas.add_dataset(set_id, set_name, space_name, times, currents, concentration, notes) 
        return space_id

    def switch_dataspace(self, space_id):
        # Get all dataspace buttons across all dataspaces
        dataspace_buttons = [widgets["dataspace_widgets"]["button_space"] for widgets in self.widgets.values()]
        # Reset stylesheet on all buttons
        for button in dataspace_buttons:
            button.setStyleSheet("background-color: rgba(128, 128, 128, 0.3)")

        # Set stylesheet on clicked button
        self.widgets[space_id]["dataspace_widgets"]["button_space"].setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")

        # Update dataspace id in canvas
        self.canvas.set_selected_space_id(space_id)

        # Show dataset widgets that are in current dataspace only
        #dataset_widgets = self.widgets[space_id]["dataset_widgets"]
        for widgets in self.widgets.values(): 
            for dataset_widgets in widgets["dataset_widgets"].values():
                for dataset_widget in dataset_widgets.values():
                    dataset_widget.hide()  
        for dataset_widgets in self.widgets[space_id]["dataset_widgets"].values():
            for dataset_widget in dataset_widgets.values():
                dataset_widget.show()

    def on_dataspace_remove_clicked(self):
        # Delete all dataspace widgets within current dataspace
        space_id = self.canvas.selected_space_id
        dataspace_widgets = self.widgets[space_id]["dataspace_widgets"]
        for widget in dataspace_widgets.values():
            widget.deleteLater()

        # Delete all dataset widgets within current dataspace
        dataset_widgets = self.widgets[space_id]["dataset_widgets"]
        for dataset_widget in dataset_widgets.values():
            for widget in dataset_widget.values():
                widget.deleteLater()

        # Remove dictionary entry
        self.widgets.pop(space_id)
        # Delete all data within current dataspace
        self.canvas.delete_selected_dataspace()

    def on_dataspace_rename_clicked(self):
        pass

    def set_active_dataspaces(self):
        checked_space_ids = []
        # Get ids of all checked boxes
        for space_id, widgets in self.widgets.items():
            if widgets["dataspace_widgets"]["checkbox_toggle"].isChecked():
                checked_space_ids.append(space_id)

        self.canvas.set_active_spaces_ids(checked_space_ids)
    
    def add_dataset_widget(self, name = None):
        set_id = self.set_widget_id
        self.set_widget_id += 1
        
        line_edit_name = QLineEdit(self)
        if name == None:
            line_edit_name.setText(f"Data {set_id}")
        else: 
            line_edit_name.setText(name)
        line_edit_name.setFixedWidth(100)
        line_edit_concentration = CustomQLineEdit(self)
        line_edit_concentration.setText("0")
        line_edit_concentration.setFixedWidth(50)
        line_edit_notes = QLineEdit(self)

        # Update dataset on text edited
        line_edit_name.textEdited.connect(lambda: self.update_dataset_info(set_id))
        line_edit_concentration.textEdited.connect(lambda: self.update_dataset_info(set_id))
        line_edit_notes.textEdited.connect(lambda: self.update_dataset_info(set_id))

        checkbox_toggle_active = QCheckBox(self)
        checkbox_toggle_active.setChecked(True)
        checkbox_toggle_active.stateChanged.connect(lambda: self.toggle_dataset(set_id))

        # Connect "paste data "button to handle_clipboard_data function
        #button_paste = QPushButton("Paste Data", self)
        #button_paste.clicked.connect(lambda: self.handle_clipboard_data(set_id))

        hbox = QHBoxLayout()
        hbox.addWidget(checkbox_toggle_active)
        hbox.addWidget(line_edit_name)
        hbox.addWidget(line_edit_concentration)
        hbox.addWidget(line_edit_notes)
        #hbox.addWidget(button_paste)

        # Add hbox to parent layout
        self.layout_datasets.addLayout(hbox)
        self.layout_datasets.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Move "add dataset" button to bottom by removing and readding it
        #if set_id > 0:
        #    self.layout_datasets.removeWidget(self.button_add_dataset)
        #self.button_add_dataset = QPushButton("Add New", self)
        #self.button_add_dataset.clicked.connect(lambda: self.add_dataset_widget())
        #self.layout_datasets.addWidget(self.button_add_dataset)

        # Store references to the widgets for later access
        dataset_widget = {
            "checkbox_toggle": checkbox_toggle_active,
            "line_edit_name": line_edit_name,
            "line_edit_concentration": line_edit_concentration,
            "line_edit_notes": line_edit_notes#,
            #"button_paste": button_paste
        }
        self.widgets[self.canvas.selected_space_id]["dataset_widgets"][set_id] = dataset_widget

        return set_id
    
    def delete_dataset_widget(self, set_id: int):   
        for widgets in self.widgets.values():
            if set_id not in widgets["dataset_widgets"]:
                continue
            # Delete widgets
            for dataset_widget in widgets["dataset_widgets"][set_id].values():
                dataset_widget.deleteLater()
            # Remove dictionary entry
            widgets["dataset_widgets"].pop(set_id)          

    def toggle_dataset(self, set_id: int):
        space_id = self.canvas.selected_space_id
        if set_id not in self.widgets[space_id]["dataset_widgets"]:
            print(f"toggle_dataset: Dataset with ID {set_id} does not exist.")
            return
              
        # Toggle widgets
        for key, widget in self.widgets[space_id]["dataset_widgets"][set_id].items():
            if key != "checkbox_toggle": # Do not toggle the checkbox itself
                widget.setEnabled(not widget.isEnabled())
        # Toggle dataset
        if widget.isEnabled():
            self.canvas.unhide_dataset(set_id)
        else:
            self.canvas.hide_dataset(set_id)

        self.setFocus() # Prevent setting focus to next widget

    def concentration_input_is_valid(self, set_id, input):
        space_id = self.canvas.selected_space_id
        concentration_widget = self.widgets[space_id]["dataset_widgets"][set_id]["line_edit_concentration"]
        # Check if input is numeric
        try:
            float(input)
            concentration_widget.setStyleSheet("")
            return True
        except ValueError:
            concentration_widget.setStyleSheet("background-color: rgba(140, 0, 0, 0.3)")
            return False

    def update_dataset_info(self, id):
        name, concentration, notes = self.get_widgets_text(id)
        if self.concentration_input_is_valid(id, concentration):
            self.canvas.update_dataset(id, name, concentration, notes)
        #self.setFocus() # Unfocus from widget

    def get_widgets_text(self, set_id):
        space_id = self.canvas.selected_space_id
        dataset_widgets = self.widgets[space_id]["dataset_widgets"][set_id]

        name = dataset_widgets["line_edit_name"].text()
        concentration = dataset_widgets["line_edit_concentration"].text()
        notes = dataset_widgets["line_edit_notes"].text()

        return name, concentration, notes

    def handle_clipboard_data(self, id):
        # Read data from clipboard
        clipboard_data = pyperclip.paste()

        if not clipboard_data:
            QMessageBox.warning(self, "No Data", "Clipboard does not contain any data.")
            return
        
        # Parse clipboard data into a DataFrame
        try:    
            data_frame = pd.read_csv(StringIO(clipboard_data), sep='\t')
            times = data_frame['time/s'].tolist()
            currents = data_frame['current/µA'].tolist()
        except Exception as e: 
            QMessageBox.warning(self, "Data in wrong format", f"No \"{e}\" found in clipboard")
            return
        
        name, concentration, notes = self.get_widgets_text(id)
        self.canvas.add_dataset(id, name, "DATASPACE0", times, currents, concentration, notes)

        print(currents)

    def on_import_data_from_csv_clicked(self):
        # Pick file to import
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("CSVs (*.csv)")
        if dialog.exec():
            filenames = dialog.selectedFiles()
            print("Selected file:", filenames)
            self.handle_csv_data(filenames)

    def handle_csv_data(self, filenames):
        # Read the CSV file into a DataFrame
        data_frame = pd.read_csv(filenames[0], encoding="utf-16", header=5)
        data_frame = data_frame.dropna()
        times = data_frame['s'].astype(float).tolist()

        # Get 'µA' columns
        current_columns = [col for col in data_frame.columns if col.startswith('µA')]

        for currents_column in current_columns:     
            id = self.add_dataset_widget()
            name, concentration, notes = self.get_widgets_text(id)
            currents = data_frame[currents_column].astype(float).tolist()
            self.canvas.add_dataset(id, name, times, currents, concentration, notes)

    def on_import_data_from_pssession_clicked(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("PSSESSION (*.pssession)")
        if not dialog.exec():
            # If user closes file picker
            return
        
        filepaths = dialog.selectedFiles()
        #print("Selected file:", filepaths)
        space_id = self.canvas.selected_space_id
        if len(self.canvas.dataspaces[space_id]["datasets"]) > 0:
            msgBox = QMessageBox()
            msgBox.setWindowTitle("Dataset Exists")
            msgBox.setText("Overwrite existing dataset?")
            msgBox.setStandardButtons(QMessageBox.StandardButton.Yes | 
                                      QMessageBox.StandardButton.No | 
                                      QMessageBox.StandardButton.Cancel)
            #msgBox.setDefaultButton(QMessageBox.Yes)
            ret = msgBox.exec()

            if ret == QMessageBox.StandardButton.Cancel:
                # Cancel action
                return
            elif ret == QMessageBox.StandardButton.Yes:
                # Delete widgets
                set_ids = list(self.widgets[space_id]["dataset_widgets"].keys())
                print(set_ids)
                for set_id in set_ids:
                    self.delete_dataset_widget(set_id)
                # Delete existing dataspace
                self.canvas.delete_selected_dataspace()
        self.handle_pssession_data(filepaths)

    def handle_pssession_data(self, filepaths):
        for filepath in filepaths:
            with open(filepath, encoding="utf-16-le") as f:
                data = f.read()
                data = data.replace("\ufeff", "")
                json_data = json.loads(data)

            times = self.extract_pssession_data_by_type(json_data, "PalmSens.Data.DataArrayTime")
            currents = self.extract_pssession_data_by_type(json_data, "PalmSens.Data.DataArrayCurrents")

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

            set_id = self.add_dataset_widget(set_name)
            _, concentration, notes = self.get_widgets_text(set_id)
            self.canvas.add_dataset(set_id, set_name, "DATASPACE 0", times, currents, concentration, notes, update_plot=False)
        self.canvas.draw_plot()

    def extract_pssession_data_by_type(self, data, target_type):
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
        
        # Extract data into list
        datavalues = None
        for measurement in data[key_measurements]:
            for value in measurement[key_dataset][key_values]:
                if value[key_type] == target_type:
                    datavalues = value[key_datavalues]
                    #print(value['datavalues'])       
        if datavalues is None:
            return
        
        values = [item[key_value] for item in datavalues]
        return values
    
class CustomQLineEdit(QLineEdit):
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selectAll()

class PlotCanvas(FigureCanvas):
    show_debug_info = True
    show_legend = True
    show_equation = True

    span = None
    span_initialized = False

    selected_space_id = 0 # Datasets within this space are drawn on the data plot
    active_spaces_ids = [0] # Results within these spaces are drawn on the results plot

    dataspaces = {} # {0: {"name": "dataspace 0", "datasets: [dataset0, dataset1]"}, 1: ...}
    #datasets = {}  # {0: {"name": "dataset 0", "times":[1,2,3], "currents":[1,2,3], "concentration":1, "notes":"foobar"}, 1: ..."}
    hidden_datasets = {}  # Storage for toggled off datasets

    def __init__(self, parent=None): 
        self.figure, (self.axes1, self.axes2) = plt.subplots(1, 2)
        super().__init__(self.figure)
        self.setParent(parent)
        #self.draw_plot()

    def set_selected_space_id(self, space_id: int):
        self.selected_space_id = space_id
        print(f"selected space: {self.selected_space_id}")
        self.draw_plot()

    def set_active_spaces_ids(self, space_ids: list):
        self.active_spaces_ids = space_ids
        print(f"active spaces: {self.active_spaces_ids}")
        self.draw_plot()

    def toggle_debug_info(self):
        self.show_debug_info = not self.show_debug_info
        self.draw_plot()
        print(f"show debug info: {self.show_debug_info}")

    def toggle_legend(self):
        self.show_legend = not self.show_legend
        self.draw_plot()
        print(f"show legend: {self.show_legend}")

    def toggle_equation(self):
        self.show_equation = not self.show_equation
        self.draw_plot()
        print(f"show equation: {self.show_equation}")

    def on_move_span(self, vmin, vmax):
        print("span:", self.span.extents)
        datasets = self.get_datasets_in_selected_dataspace()
        if len(datasets) > 1: 
            self.draw_plot()

    def create_span_selector(self, snaps):
        self.span = SpanSelector(
            self.axes1, 
            self.on_move_span,
            'horizontal', 
            useblit=True, # For faster canvas updates
            interactive=True, # Allow resizing by dragging from edges
            drag_from_anywhere=True, # Allow moving by dragging
            props=dict(alpha=0.2, facecolor="tab:blue"), # Visuals
            ignore_event_outside=True, # Keep the span displayed after interaction
            grab_range=6,
            snap_values=snaps) # Snap to time values  

    def update_dataset(self, set_id, name, concentration, notes):
        datasets = self.get_datasets_in_selected_dataspace()
        if set_id in datasets:
            # Update concentration and notes for the specified dataset
            datasets[set_id]['name'] = name
            datasets[set_id]['concentration'] = float(concentration)
            datasets[set_id]['notes'] = notes

            self.draw_plot()
            print(datasets[set_id]["name"])
        else:
            print(f"update_dataset: Dataset with id '{set_id}' does not exist.")

    def add_dataset(self, set_id, set_name, space_name, times, currents, concentration, notes, update_plot = True):         
        dataset = {
            "name": set_name,
            'times': times,
            'currents': currents,
            'concentration': float(concentration),
            'notes': notes
        }

        # Create new dataspace if id doesnt exist
        if self.selected_space_id not in self.dataspaces:
            self.dataspaces[self.selected_space_id] = {
                "name": space_name, 
                "datasets": {}
            } 

        datasets = self.get_datasets_in_selected_dataspace()
        if set_id in datasets:
            print(f"add_dataset: Dataset with id '{set_id}' already exists. Dataset overwritten")

        # Add dataset to dataspace
        datasets[set_id] = dataset

        if not self.span_initialized: 
            self.initialize_span(times)
        if update_plot:
            self.draw_plot()

    def get_datasets_in_selected_dataspace(self):
        if self.selected_space_id in self.dataspaces:
            datasets = self.dataspaces[self.selected_space_id]["datasets"]
            return datasets
        else:
            return None
    
    def get_datasets_in_active_dataspaces(self):      
        active_datasets = [self.dataspaces[active_id]["datasets"] for active_id in self.active_spaces_ids if active_id in self.dataspaces]
        return active_datasets
        
    def delete_dataset(self, dataset_id):
        pass
    
    def delete_selected_dataspace(self):
        self.dataspaces.pop(self.selected_space_id)
        self.span_initialized = False
        self.draw_plot()

    def hide_dataset(self, set_id):
        datasets = self.get_datasets_in_selected_dataspace()   
        if set_id not in datasets:
            print(f"hide_dataset: Dataset with id '{set_id}' does not exist.")
            return
        
        self.hidden_datasets[set_id] = datasets.pop(set_id)
        self.draw_plot()
    
    def unhide_dataset(self, set_id):
        datasets = self.get_datasets_in_selected_dataspace()   
        if set_id not in self.hidden_datasets:
            print(f"unhide_dataset: Dataset with id '{set_id}' does not exist.")
            return
        
        datasets[set_id] = self.hidden_datasets.pop(set_id)
        self.draw_plot()

    def initialize_span(self, times):  
        self.create_span_selector(np.array(times)) # Time values from first dataset
        last_value = times[-1]
        span_right = last_value
        span_left = round(float(last_value) * 0.9, ndigits=1)
        self.span.extents = (span_left, span_right)
        self.span_initialized = True
        
    def plot_results(self): 
        active_datasets = self.get_datasets_in_active_dataspaces()
        #print(active_datasets[0]["name"])
        #datasets = self.get_datasets_in_selected_dataspace()
        #if datasets == None:
            #return
        if len(active_datasets) == 0:
            self.axes2.clear()
            return
        
        results = []
        for dataset in active_datasets:
            result = self.calculate_results(dataset)
            results.append(result)

        self.axes2.clear()
        default_color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
        dataspace_names = [self.dataspaces[space_id]["name"] for space_id in self.active_spaces_ids if space_id in self.dataspaces] # active_datasets or results doesnt have dataspace names. fix later

        for i, result in enumerate(results):
            if result == None:
                return
            
            if len(result) < 2:
                self.axes2.clear()
                self.axes2.set_ylabel("current(µA)")
                self.axes2.set_xlabel("concentration(mM)")
                info_text = "Add atleast 2 different concentrations"
                self.axes2.text(0.5, 0.5, info_text, fontsize=10, horizontalalignment="center", verticalalignment="center", transform=self.axes2.transAxes)
                return
            
            # Unpack data
            concentrations, calculated_currents = zip(*result)
            avg_currents, std_currents = zip(*calculated_currents)

            # Perform linear regression to get slope, intercept, and R-squared
            slope, intercept = np.polyfit(concentrations, avg_currents, 1)
            r_squared = np.corrcoef(concentrations, avg_currents)[0, 1]**2
            trendline = slope * np.array(concentrations) + intercept

            # Plot the data
            self.axes2.errorbar(concentrations, avg_currents, yerr=std_currents, marker="o", capsize=3, label=dataspace_names[i], color=default_color_cycle[i])
            self.axes2.plot(concentrations, trendline, linestyle="--", color=default_color_cycle[i])

            # Display the equation
            if self.show_equation:
                equation_text = f"y = {slope:.4f}x + {intercept:.4f}"
                r_squared_text = f"R² = {r_squared:.6f}"
                self.axes2.text(0.1, i / 10 + 0.1, 
                                f"{equation_text}\n{r_squared_text}", 
                                fontsize=12, 
                                bbox=dict(facecolor=default_color_cycle[i], alpha=0.3), 
                                horizontalalignment="left", verticalalignment="center", 
                                transform=self.axes2.transAxes)

        # Set legend, grind, set labels
        if self.show_legend:
            self.axes2.legend()
        self.axes2.grid(True)
        self.axes2.set_ylabel("current(µA)")
        self.axes2.set_xlabel("concentration(mM)")
        
        # Set tick locations
        x_ticks = np.arange(start=min(concentrations), stop=max(concentrations) + 1)
        #print(concentrations)
        #print(x_ticks)
        self.axes2.xaxis.set_major_locator(plt.AutoLocator())
        #self.axes2.xaxis.set_minor_locator(plt.AutoMinorLocator())
        self.axes2.yaxis.set_major_locator(plt.MaxNLocator(10))

        #if len(results) == 1:
        if self.show_debug_info and len(results) == 1:
            self.draw_debug_box(concentrations, avg_currents, std_currents, slope, intercept, trendline)
            #print(sorted_concentration_data)

    def calculate_results(self, datasets):
        # Iterate over each dataset
        concentration_data = {}
        for data in datasets.values():
            # Convert lists to numpy arrays
            times = np.array(data["times"])
            currents = np.array(data["currents"])
            concentration = data["concentration"]

            # Find indices where times fall within the specified range
            indices = np.where((times >= self.span.extents[0]) & (times <= self.span.extents[1]))[0]

            # Calculate the average current for the specified range
            avg_current = np.mean(currents[indices])

            if concentration in concentration_data:
                concentration_data[concentration].append(avg_current)
            else:
                concentration_data[concentration] = [avg_current]
        #print(f"RAW: {concentration_data}")
        
        # Calculate average of average currents for each concentration
        for concentration, currents_list in concentration_data.items():
            concentration_data[concentration] = (np.mean(currents_list), np.std(currents_list))

        sorted_concentration_data = sorted(concentration_data.items())

        return sorted_concentration_data

    def plot_data(self):
        # Clear existing plot
        self.axes1.clear()

        datasets = self.get_datasets_in_selected_dataspace()
        if datasets == None:
            self.axes1.grid(True)
            self.draw()
            #print("no datasets")
            return
        
        # Plot each dataset      
        for data in datasets.values():
            times = data['times']
            currents = data['currents']
            name = data['name']
            self.axes1.plot(times, currents, label=name)
        
        # Set legend, grind, set labels
        if self.show_legend:
            self.axes1.legend()
        self.axes1.grid(True)
        self.axes1.set_ylabel("current(µA)")
        self.axes1.set_xlabel("time(s)")
        
        # Set tick locations
        self.axes1.xaxis.set_major_locator(plt.MaxNLocator(10))
        self.axes1.yaxis.set_major_locator(plt.MaxNLocator(10))

    def draw_plot(self):    
        self.plot_data()
        self.plot_results()
        self.figure.tight_layout()
        self.draw()
        print(f"draw_plot called")     
    
    def draw_debug_box(self, concentrations, avg_currents, std_currents, slope, intercept, trendline):
        concentrations_text = f"CONCENTRATIONS: {concentrations}"
        avgs_text = f"AVGS: {np.round(avg_currents, decimals=5)}"
        stds_text = f"STDS: {np.round(std_currents, decimals=5)}"
        slope_text = f"SLOPE: {slope}"
        intercept_text = f"INTERCEPT: {intercept}"
        trendline_text = f"TRENDLINE: {np.round(trendline, decimals=5)}"
        self.axes2.text(0.1, 0.9, 
                        f"{concentrations_text}\n{avgs_text}\n{stds_text}\n{slope_text}\n{intercept_text}\n{trendline_text}", 
                        fontsize=8, 
                        bbox=dict(facecolor="blue", alpha=0.2), 
                        horizontalalignment="left", verticalalignment="center", 
                        transform=self.axes2.transAxes)
        
def main():
    app = QApplication(sys.argv)
    window = MyMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
