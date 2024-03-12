import json
import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QFileDialog, QCheckBox
from PyQt6.uic import loadUi
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector, SpanSelector
import numpy as np
import pandas as pd
import pyperclip
from io import StringIO

class MyMainWindow(QMainWindow):
    widget_id = 0
    dataset_widgets = {} # {1: (name1, concentration1, notes1), 2: (name2, concentration2, notes2), ...}

    def __init__(self):
        super().__init__()
        loadUi("amp_helper.ui", self)

        self.pushButton_add_dataset.clicked.connect(lambda: self.add_dataset_widget())
        self.actionImport_data_from_CSV.triggered.connect(self.on_import_data_from_csv_clicked)
        self.actionImport_data_from_PSSESSION.triggered.connect(self.on_import_data_from_pssession_clicked)

        # Bidirectional connection for plot seconds slider and lineEdit
        self.horizontalSlider_plot_seconds.valueChanged.connect(lambda value, le=self.lineEdit_plot_seconds: le.setText(str(value)))
        self.lineEdit_plot_seconds.editingFinished.connect(lambda: self.horizontalSlider_plot_seconds.setValue(int(self.lineEdit_plot_seconds.text())))

        self.canvas = PlotCanvas(self.plotWidget)
        layout = QVBoxLayout(self.plotWidget)
        layout.addWidget(self.canvas)
        layout.setContentsMargins(2, 2, 2, 2)

        navigation_toolbar = NavigationToolbar(self.canvas, self)
        #navigation_toolbar.setStyleSheet("QToolBar { border: 0px; }")
        self.verticalLayout_toolbox.addWidget(navigation_toolbar)

        #self.add_dataset_widget()

    def add_dataset_widget(self, name = None):
        id = self.widget_id
        self.widget_id += 1
        
        line_edit_name = QLineEdit(self)
        if name == None:
            line_edit_name.setText(f"Data {id}")
        else: 
            line_edit_name.setText(name)
        line_edit_concentration = CustomQLineEdit(self)
        line_edit_concentration.setText("0")
        line_edit_notes = QLineEdit(self)

        # Update data data on editing finished
        line_edit_name.textEdited.connect(lambda: self.update_dataset_info(id))
        line_edit_concentration.textEdited.connect(lambda: self.update_dataset_info(id))
        line_edit_notes.textEdited.connect(lambda: self.update_dataset_info(id))

        checkbox_toggle_active = QCheckBox(self)
        checkbox_toggle_active.setChecked(True)
        checkbox_toggle_active.stateChanged.connect(lambda: self.toggle_dataset(id))

        # Connect button click to handle_clipboard_data function
        button_paste = QPushButton("Paste Data", self)
        button_paste.clicked.connect(lambda: self.handle_clipboard_data(id))
                                     
        hbox = QHBoxLayout()
        hbox.addWidget(checkbox_toggle_active)
        hbox.addWidget(line_edit_name)
        hbox.addWidget(line_edit_concentration)
        hbox.addWidget(line_edit_notes)
        hbox.addWidget(button_paste)

        # Add hbox to parent layout
        self.verticalLayout_datasets.addLayout(hbox)
        self.verticalLayout_datasets.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Store references to the widgets for later access
        self.dataset_widgets[id] = {
            "checkbox_toggle": checkbox_toggle_active,
            "line_edit_name": line_edit_name,
            "line_edit_concentration": line_edit_concentration,
            "line_edit_notes": line_edit_notes,
            "button_paste": button_paste
        }

        return id
    
    def toggle_dataset(self, id):
        if id not in self.dataset_widgets:
            print(f"Dataset with ID {id} does not exist.")
            return
        
        for key, widget in self.dataset_widgets[id].items():
            if key != "checkbox_toggle": # Do not disable the checkbox itself
                widget.setEnabled(not widget.isEnabled())
        if widget.isEnabled():
            self.canvas.unhide_dataset(id)
        else:
            self.canvas.hide_dataset(id)
        self.setFocus() # Prevent setting focus to next widget
        print(self.canvas.datasets.keys())
        print(self.canvas.hidden_datasets.keys())

    def concentration_input_is_valid(self, id, input):
        concentration_widget = self.dataset_widgets[id]["line_edit_concentration"]
        if input.isdigit():
            concentration_widget.setStyleSheet("")
            return True
        else:
            concentration_widget.setStyleSheet("background-color: rgba(140, 0, 0, 0.3)")
            return False

    def update_dataset_info(self, id):
        name, concentration, notes = self.get_widgets_text(id)
        if self.concentration_input_is_valid(id, concentration):
            self.canvas.update_dataset(id, name, concentration, notes)
        #self.setFocus() # Unfocus from widget

    def get_widgets_text(self, id):
        widgets = self.dataset_widgets[id]
        name = widgets["line_edit_name"].text()
        concentration = widgets["line_edit_concentration"].text()
        notes = widgets["line_edit_notes"].text()

        return name, concentration, notes

    def handle_clipboard_data(self, id):
        # Read data from clipboard
        clipboard_data = pyperclip.paste()

        if not clipboard_data:
            QMessageBox.warning(self, "No Data", "Clipboard does not contain any data.")
            return
        
        try:
            # Parse clipboard data into a DataFrame
            data_frame = pd.read_csv(StringIO(clipboard_data), sep='\t')
            times = data_frame['time/s'].tolist()
            print(times)
            currents = data_frame['current/µA'].tolist()
        except Exception as e: 
            QMessageBox.warning(self, "Error", "Data is in wrong format.")
            print(e)
            return
        
        name, concentration, notes = self.get_widgets_text(id)
        self.canvas.add_dataset(id, name, times, currents, concentration, notes)

    def on_import_data_from_csv_clicked(self):
        # pick file to import
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
        if dialog.exec():
            filepaths = dialog.selectedFiles()
            print("Selected file:", filepaths)
            self.handle_pssession_data(filepaths)

    def handle_pssession_data(self, filepaths):
        for filepath in filepaths:
            with open(filepath, encoding="utf-16-le") as f:
                data = f.read()
                data = data.replace("\ufeff", "")
                json_data = json.loads(data)
            times = self.find_pssession_datavalues_by_type(json_data, "PalmSens.Data.DataArrayTime")
            currents = self.find_pssession_datavalues_by_type(json_data, "PalmSens.Data.DataArrayCurrents")
            
            filename = os.path.basename(filepath)
            name = filename.split(".")[0]
            id = self.add_dataset_widget(name)
            name, concentration, notes = self.get_widgets_text(id)
            self.canvas.add_dataset(id, name, times, currents, concentration, notes)

    def find_pssession_datavalues_by_type(self, data, target_type):
        datavalues = None
        for measurement in data['measurements']:
            for value in measurement['dataset']['values']:
                if value['type'] == target_type:
                    datavalues = value['datavalues']
                    #print(value['datavalues'])       
        if datavalues is None:
            return
        
        values = [item['v'] for item in datavalues]
        return values
    
class CustomQLineEdit(QLineEdit):
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selectAll()

class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None): 
        self.figure, (self.axes1, self.axes2) = plt.subplots(1, 2)
        self.figure.tight_layout(pad=0.4)
        super().__init__(self.figure)
        self.setParent(parent)

        self.span = None
        self.span_initialized = False
        self.datasets = {}  # {"0": {"times":[1,2,3], "currents":[1,2,3], "concentration":1, "notes":"foobar"}, "1": ..."}
        self.hidden_datasets = {}  # {"0": {"times":[1,2,3], "currents":[1,2,3], "concentration":1, "notes":"foobar"}, "1": ..."}

    def onselect(self, vmin, vmax):
        print("span:", self.span.extents)
        if len(self.datasets) > 1: self.draw_plot()

    def create_span_selector(self, snaps):
        self.span = SpanSelector(
            self.axes1, 
            self.onselect,
            'horizontal', 
            useblit=True, # For faster canvas updates
            interactive=True, # Allow resizing by dragging from edges
            drag_from_anywhere=True, # Allow moving by dragging
            props=dict(alpha=0.2, facecolor="tab:blue"), # Visuals
            ignore_event_outside=True, # Keep the span displayed after interaction
            grab_range=6,
            snap_values=snaps) # Snap to time values  

    def update_dataset(self, id, name, concentration, notes):
        if id in self.datasets:
            # Update concentration and notes for the specified dataset
            self.datasets[id]['name'] = name
            self.datasets[id]['concentration'] = float(concentration)
            self.datasets[id]['notes'] = notes

            self.draw_plot()
            print(self.datasets[id]["name"])
        else:
            print(f"Dataset with id '{id}' does not exist.")

    def add_dataset(self, id, name, times, currents, concentration, notes):
        if id in self.datasets:
            print(f"Dataset with id '{id}' already exists. Dataset overwritten")
            
        self.datasets[id] = {
            "name": name,
            'times': times,
            'currents': currents,
            'concentration': float(concentration),
            'notes': notes
        }
        self.draw_plot()
        if not self.span_initialized: 
            self.initialize_span(times)

    def hide_dataset(self, id):
        if id not in self.datasets:
            print(f"hide_dataset: Dataset with id '{id}' does not exist.")
            return
        self.hidden_datasets[id] = self.datasets.pop(id)
        self.draw_plot()
    
    def unhide_dataset(self, id):
        if id not in self.hidden_datasets:
            print(f"unhide_dataset: Dataset with id '{id}' does not exist.")
            return
        self.datasets[id] = self.hidden_datasets.pop(id)
        self.draw_plot()

    def initialize_span(self, times):  
        self.create_span_selector(np.array(times)) # Time values from first dataset
        last_value = times[-1]
        span_right = last_value
        span_left = round(float(last_value) * 0.9, ndigits=1)
        self.span.extents = (span_left, span_right)
        self.span_initialized = True
        
    def plot_results(self):
        concentration_data = {}
        # Iterate over each dataset
        for label, data in self.datasets.items():
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
        print(f"RAW: {concentration_data}")

        if len(concentration_data) < 2:
            info_text = "Add atleast 2 different concentrations"
            self.axes2.text(0.5, 0.5, info_text, fontsize=10, horizontalalignment="center", verticalalignment="center", transform=self.axes2.transAxes)
            return
        
        # Calculate average of average currents for each concentration
        for concentration, currents_list in concentration_data.items():
            concentration_data[concentration] = (np.mean(currents_list), np.std(currents_list))

        sorted_concentration_data = sorted(concentration_data.items())
        concentrations, calculated_currents = zip(*sorted_concentration_data)
        avg_currents, std_currents = zip(*calculated_currents)

        print(f"CALCULATED: {sorted_concentration_data}")
        print(f"AVGS: {avg_currents}")
        print(f"STDS: {std_currents}")

        # Perform linear regression to get slope, intercept, and R-squared
        slope, intercept = np.polyfit(concentrations, avg_currents, 1)
        r_squared = np.corrcoef(concentrations, avg_currents)[0, 1]**2
        trendline = slope * np.array(concentrations) + intercept

        # Clear existing plot
        self.axes2.clear()

        # Display the equation
        equation_text = f"y = {slope:.4f}x + {intercept:.4f}"
        r_squared_text = f"R² = {r_squared:.4f}"
        self.axes2.text(0.2, 0.2, 
                        f"{equation_text}\n{r_squared_text}", 
                        fontsize=12, 
                        bbox=dict(facecolor="orange", alpha=0.3), 
                        horizontalalignment="center", verticalalignment="center", 
                        transform=self.axes2.transAxes)

        # Plot the data
        self.axes2.errorbar(concentrations, avg_currents, yerr=std_currents, marker="o", capsize=3, label="Data")
        self.axes2.plot(concentrations, trendline, linestyle="--", label="Trendline")

        # Turn grid on and set labels
        self.axes2.grid(True)
        self.axes2.set_ylabel("current(µA)")
        self.axes2.set_xlabel("concentration(mM)")

        # Set tick locations
        x_ticks = np.arange(start=min(concentrations), stop=max(concentrations) + 1)
        self.axes2.xaxis.set_major_locator(plt.FixedLocator(x_ticks))
        self.axes2.yaxis.set_major_locator(plt.MaxNLocator(10))

    def plot_data(self):
        # Clear existing plot
        self.axes1.clear()

        # Plot each dataset
        for label, data in self.datasets.items():
            times = data['times']
            currents = data['currents']
            name = data['name']
            self.axes1.plot(times, currents, label=name)
        
        # Turn on legend and grind and set labels
        self.axes1.legend()
        self.axes1.grid(True)
        self.axes1.set_ylabel("current(µA)")
        self.axes1.set_xlabel("time(s)")
        
        # Set tick locations
        self.axes1.xaxis.set_major_locator(plt.MaxNLocator(10))
        self.axes1.yaxis.set_major_locator(plt.MaxNLocator(10))

    def draw_plot(self):
        self.plot_data()
        if len(self.datasets) > 1: 
            self.plot_results()
        self.draw()

def main():
    app = QApplication(sys.argv)
    window = MyMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
