import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
from PyQt6.uic import loadUi
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
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

        self.canvas = PlotCanvas(self.plotWidget)
        layout = QVBoxLayout(self.plotWidget)
        layout.addWidget(self.canvas)

        navigation_toolbar = NavigationToolbar(self.canvas, self)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, navigation_toolbar)

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
            times = data['time/s']
            currents = data['current/µA']
        except Exception as e: 
            QMessageBox.warning(self, "Error", "Data is in wrong format.")
            print(e)
            return
        
        #print(len(times))
        #print(len(currents))
        self.canvas.add_dataset(name, times, currents)


    def parse_clipboard_data(self):
        # Read data from clipboard
        clipboard_data = pyperclip.paste()

        if not clipboard_data:
            return None
        
        # Parse clipboard data into a DataFrame
        data_frame = pd.read_csv(StringIO(clipboard_data), sep='\t')

        return data_frame

class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100): 
        self.figure, self.axes = plt.subplots()
        super().__init__(self.figure)
        self.setParent(parent)
        self.datasets = {}  # Dictionary to store datasets
        #self.draw_plot()

    def add_dataset(self, label, x, y):
        # Add a new dataset or update existing one
        self.datasets[label] = (x, y)

        # Clear existing plot
        self.axes.clear()

        # Plot each dataset
        for label, data in self.datasets.items():
            x, y = data
            self.axes.plot(x, y, label=label)
            #import numpy as np; import pandas as pd; import pyperclip; pyperclip.copy(pd.DataFrame(np.array(y).reshape(-1,1)).to_csv(index=False, header=False))
            #print(y)
        
        # Set title and legend and turn on grid
        self.axes.set_title('Matplotlib Plot')
        self.axes.legend()
        self.axes.grid(True)

        # Set labels for axes
        self.axes.set_ylabel("current/µA")
        self.axes.set_xlabel("time/s")

        '''Set y-axis limits to the closest integers
        y_values = [float(val) for _, y in self.datasets.values() for val in y]
        min_y = round(min(y_values) - 1)
        max_y = round(max(y_values) + 1)
        print((min_y, max_y))
        #self.axes.set_ylim([min_y, max_y])
        #self.axes.set_ylim(bottom=-25)'''
        
        # Set number of ticks on the x and y axes
        self.axes.xaxis.set_major_locator(plt.MaxNLocator(10))
        self.axes.yaxis.set_major_locator(plt.MaxNLocator(10))

        self.draw()

        print(self.datasets.keys())

def main():
    app = QApplication(sys.argv)
    window = MyMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
