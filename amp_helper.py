import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
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

        self.pushButton_add_dataset.clicked.connect(self.on_button_add_dataset_clicked)

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

        self.on_button_add_dataset_clicked()

    def on_button_add_dataset_clicked(self):
        line_edit_name = QLineEdit(self)
        line_edit_name.setText(f"Data {self.data_index}")
        line_edit_concentration = QLineEdit(self)
        line_edit_concentration.setText("3")
        line_edit_notes = QLineEdit(self)

        # Store references to the line edit widgets for later access
        self.line_edit_widgets.append((line_edit_name, line_edit_concentration, line_edit_notes))

        # Connect button click to handle_data function
        button = QPushButton("Paste Data", self)
        button.clicked.connect(lambda: self.handle_data(line_edit_name.text(), line_edit_concentration.text(), line_edit_notes.text()))

        hbox = QHBoxLayout()
        hbox.addWidget(line_edit_name)
        hbox.addWidget(line_edit_concentration)
        hbox.addWidget(line_edit_notes)
        hbox.addWidget(button)

        # Add the QLineEdit widget to the vertical layout named verticalLayout_datasets
        self.verticalLayout_datasets.addLayout(hbox)

        # Set alignment to top
        self.verticalLayout_datasets.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.data_index += 1

    def handle_data(self, name, concentration, notes):
        data = self.parse_clipboard_data()

        if data is None:
            QMessageBox.warning(self, "No Data", "Clipboard does not contain any data.")
            return

        try:
            times = data['time/s'].tolist()
            currents = data['current/µA'].tolist()
        except Exception as e: 
            QMessageBox.warning(self, "Error", "Data is in wrong format.")
            print(e)
            return
        
        #print(len(times))
        #print(len(currents))
        self.canvas.add_dataset(name, times, currents, concentration, notes)


    def parse_clipboard_data(self):
        # Read data from clipboard
        clipboard_data = pyperclip.paste()

        if not clipboard_data:
            return None
        
        # Parse clipboard data into a DataFrame
        data_frame = pd.read_csv(StringIO(clipboard_data), sep='\t')

        return data_frame

class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None): 
        self.figure, (self.axes1, self.axes2) = plt.subplots(1, 2)
        super().__init__(self.figure)
        self.setParent(parent)
        #self.figure.subplots_adjust(left=0.1, right=0.98, bottom=0.08, top=0.98)
        self.figure.tight_layout(pad=0.4)
        #self.figure.subplots_adjust(hspace=0.5)

        self.datasets = {}  # Dictionary to store datasets
        self.span = None
        self.span_initialized = False

    def onselect(self, vmin, vmax):
        print("span:", self.span.extents)
        if len(self.datasets) > 1: self.plot_results() # EI PÄIVITÄ

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
        
    def add_dataset(self, label, times, currents, concentration, notes):
        # Add a new dataset or update existing one
        self.datasets[label] = (times, currents, concentration, notes)
        print(self.datasets[label][2])

        self.plot_data()
        if len(self.datasets) > 1: 
            self.plot_results()
        self.draw()

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
        # Initialize lists to store the average current and concentration
        avg_currents = []
        concentrations = []

        # Iterate over each dataset
        for times, currents, concentration, _ in self.datasets.values():
            # Convert lists to numpy arrays
            times = np.array(times)
            currents = np.array(currents)

            # Find indices where times fall within the specified range
            indices = np.where((times >= self.span.extents[0]) & (times <= self.span.extents[1]))[0]

            # Calculate the average current for the specified range
            avg_current = np.mean(currents[indices])

            # Append the average current and concentration to the lists
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
            times, currents, concentration, notes = data
            self.axes1.plot(times, currents, label=label)
            #import numpy as np; import pandas as pd; import pyperclip; pyperclip.copy(pd.DataFrame(np.array(y).reshape(-1,1)).to_csv(index=False, header=False))
            #print(y)
        
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


def main():
    app = QApplication(sys.argv)
    window = MyMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
