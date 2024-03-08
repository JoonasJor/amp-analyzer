import json
import os
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QFileDialog
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
    data_index = 0
    line_edit_widgets = [] # [(name1, concentration1, notes1), (name2, concentration2, notes2), ...]

    def __init__(self):
        super().__init__()
        loadUi("amp_helper.ui", self)

        self.pushButton_add_dataset.clicked.connect(self.add_dataset_widget)
        self.actionImport_data_from_CSV.triggered.connect(self.on_import_data_from_csv_clicked)
        self.actionImport_data_from_PSSESSION.triggered.connect(self.on_import_data_from_pssession_clicked)

        # Bidirectional connection for plot seconds slider and lineEdit
        self.horizontalSlider_plot_seconds.valueChanged.connect(lambda value, le=self.lineEdit_plot_seconds: le.setText(str(value)))
        self.lineEdit_plot_seconds.editingFinished.connect(lambda: self.horizontalSlider_plot_seconds.setValue(int(self.lineEdit_plot_seconds.text())))

        self.canvas = PlotCanvas(self.plotWidget)
        layout = QVBoxLayout(self.plotWidget)
        layout.addWidget(self.canvas)
        layout.setContentsMargins(2, 2, 2, 2)  # Set margins to 0

        navigation_toolbar = NavigationToolbar(self.canvas, self)
        #navigation_toolbar.setStyleSheet("QToolBar { border: 0px; }")
        self.verticalLayout_toolbox.addWidget(navigation_toolbar)

        #self.add_dataset_widget()

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

        #s = open(filenames[0], mode='r', encoding='utf-8-sig').read()
        #open(filenames[0], mode='w', encoding='utf-8').write(s)

        # Read the CSV file into a DataFrame
        data_frame = pd.read_csv(filenames[0], encoding="utf-16", header=5)
        data_frame = data_frame.dropna()
        #print(data_frame)

        # Replace BOM character and convert to float list
        #times = data_frame['s'].str.replace('\ufeff', '')
        #print(data_frame['s'].tolist())
        times = data_frame['s'].astype(float).tolist()
        #times = [float(time) for time in times]
        #print(times[0][1:])
        #times[0] = times[0][1:]
        #times = times.apply(pd.to_numeric)
        #print(times)

        # Get 'µA' columns
        current_columns = [col for col in data_frame.columns if col.startswith('µA')]

        for currents_column in current_columns:     
            name, concentration, notes = self.add_dataset_widget()

            currents = data_frame[currents_column].astype(float).tolist()
            #print(currents)
            #currents = [float(current) for current in currents]
            self.canvas.add_dataset(name, times, currents, concentration, notes)

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
            times = self.find_datavalues_by_type(json_data, "PalmSens.Data.DataArrayTime")
            currents = self.find_datavalues_by_type(json_data, "PalmSens.Data.DataArrayCurrents")

            
            filename = os.path.basename(filepath)
            name = filename.split(".")[0]
            _, concentration, notes = self.add_dataset_widget(name)
            self.canvas.add_dataset(name, times, currents, concentration, notes)

    def add_dataset_widget(self, name = None):
        #print(self.line_edit_widgets)
        line_edit_name = QLineEdit(self)
        if name == None:
            line_edit_name.setText(f"Data {self.data_index}")
        else: 
            line_edit_name.setText(name)
        line_edit_concentration = QLineEdit(self)
        line_edit_concentration.setText("3")
        line_edit_notes = QLineEdit(self)

        # Store references to the line edit widgets for later access
        self.line_edit_widgets.append((line_edit_name, line_edit_concentration, line_edit_notes))

        line_edit_concentration.editingFinished.connect(lambda: self.update_data(line_edit_name.text(), 
                                                                                line_edit_concentration.text(), 
                                                                                line_edit_notes.text()))
        # Connect button click to handle_clipboard_data function
        button_paste = QPushButton("Paste Data", self)
        button_paste.clicked.connect(lambda: self.handle_clipboard_data(line_edit_name.text(), 
                                                                        line_edit_concentration.text(), 
                                                                        line_edit_notes.text()))
        hbox = QHBoxLayout()
        hbox.addWidget(line_edit_name)
        hbox.addWidget(line_edit_concentration)
        hbox.addWidget(line_edit_notes)
        hbox.addWidget(button_paste)

        # Add the QLineEdit widget to the vertical layout named verticalLayout_datasets
        self.verticalLayout_datasets.addLayout(hbox)

        # Set alignment to top
        self.verticalLayout_datasets.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.data_index += 1

        return line_edit_name.text(), line_edit_concentration.text(), line_edit_notes.text()
    
    def find_datavalues_by_type(self, data, target_type):
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

    def update_data(self, name, concentration, notes):
        if concentration.isdigit():
            self.canvas.update_dataset(name, concentration, notes)
        
    def handle_clipboard_data(self, name, concentration, notes):
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
        
        self.canvas.add_dataset(name, times, currents, concentration, notes)

class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None): 
        self.figure, (self.axes1, self.axes2) = plt.subplots(1, 2)
        self.figure.tight_layout(pad=0.4)
        super().__init__(self.figure)
        self.setParent(parent)

        self.span = None
        self.span_initialized = False
        self.datasets = {}  # {"dataset 0": {"times":[1,2,3], "currents":[1,2,3], "concentration":1, "notes":"foobar"}, "dataset 1": ..."}

    def onselect(self, vmin, vmax):
        print("span:", self.span.extents)
        if len(self.datasets) > 1: self.draw_plot()

    def create_span_selector(self, snaps):
        self.span = SpanSelector(self.axes1, 
                                 self.onselect,
                                 'horizontal', 
                                 useblit=True, # For faster canvas updates
                                 interactive=True, # Allow resizing by dragging from edges
                                 drag_from_anywhere=True, # Allow moving by dragging
                                 props=dict(alpha=0.2, facecolor="tab:blue"), # Visuals
                                 ignore_event_outside=True, # Keep the span displayed after interaction
                                 grab_range=6,
                                 snap_values=snaps) # Snap to time values  

    def update_dataset(self, name, concentration, notes):
        if name in self.datasets:
            # Update concentration and notes for the specified dataset
            self.datasets[name]['concentration'] = concentration
            self.datasets[name]['notes'] = notes

            self.draw_plot()
        else:
            print(f"Dataset with name '{name}' does not exist.")

    def add_dataset(self, label, times, currents, concentration, notes):
        # Add a new dataset or overwrite existing one
        self.datasets[label] = {
            'times': times,
            'currents': currents,
            'concentration': concentration,
            'notes': notes
        }

        self.draw_plot()

        # Set initial span coords
        if not self.span_initialized: 
            self.create_span_selector(np.array(times)) # Time values from first dataset
            last_value = times[-1]
            span_right = last_value
            span_left = round(float(last_value) * 0.9, ndigits=1)
            self.span.extents = (span_left, span_right)
            self.span_initialized = True
            #print(self.span.extents)
        
    def plot_results(self):
        avg_currents = []
        concentrations = []
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
            print(concentration_data)

        # Calculate average currents for each concentration
        for concentration, currents_list in concentration_data.items():
            avg_current = np.mean(currents_list)
            avg_currents.append(avg_current)
            concentrations.append(concentration)

        # Convert lists to numpy arrays
        avg_currents = np.array(avg_currents)
        concentrations = np.array(concentrations, dtype=float)
        x_ticks = np.arange(start=min(concentrations), stop=max(concentrations) + 1)
        #print(x_values)

        self.axes2.clear()
        self.axes2.plot(concentrations, avg_currents, marker='o')
        self.axes2.grid(True)
        self.axes2.set_ylabel("current(µA)")
        self.axes2.set_xlabel("concentration(mM)")
        self.axes2.xaxis.set_major_locator(plt.FixedLocator(x_ticks))
        self.axes2.yaxis.set_major_locator(plt.MaxNLocator(10))

    def plot_data(self):
        # Clear existing plot
        self.axes1.clear()

        # Plot each dataset
        for label, data in self.datasets.items():
            times = data['times']
            currents = data['currents']
            self.axes1.plot(times, currents, label=label)
        
        # Set title and legend and turn on grid
        #self.axes.set_title('Matplotlib Plot')
        self.axes1.legend()
        self.axes1.grid(True)

        # Set labels for axes
        self.axes1.set_ylabel("current(µA)")
        self.axes1.set_xlabel("time(s)")
        
        # Set number of ticks on the x and y axes
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
