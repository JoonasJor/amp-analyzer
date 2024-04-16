import json
import os
import sys
import traceback
import numpy as np
import pandas as pd
import pyperclip
import pickle
from threading import Timer
from datetime import datetime
from io import StringIO
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QFileDialog, QCheckBox, QApplication
from PyQt6.uic import loadUi
from PyQt6.QtCore import Qt, QFileInfo, pyqtSignal
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.widgets import SpanSelector
from matplotlib.axes import Axes
import matplotlib.colors as mcolors


class MyMainWindow(QMainWindow):
    space_widget_id = 0
    set_widget_id = 0
    layout_datasets: QVBoxLayout
    layout_dataspaces: QVBoxLayout
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

        loadUi("amp_analyzer.ui", self)
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
        self.actionSave.triggered.connect(lambda: self.on_save_clicked(ask_for_file_location=False))
        self.actionSave_as.triggered.connect(lambda: self.on_save_clicked(ask_for_file_location=True))
        self.actionLoad.triggered.connect(lambda: self.on_load_clicked(ask_for_file_location=True))

        # Dataspace button signals
        self.pushButton_dataspace_add.clicked.connect(lambda: self.add_dataspace_widget(initialize_dataset=True))
        self.pushButton_dataspace_remove.clicked.connect(lambda:self.on_dataspace_remove_clicked())
        self.pushButton_dataspace_rename.clicked.connect(lambda:self.on_dataspace_rename_clicked())

        # Current to concentration signal
        self.lineEdit_convert_current.textChanged.connect(lambda: self.find_concentration_from_current(self.lineEdit_convert_current.text()))

        # Dataspace notes signal
        self.plainTextEdit_space_notes.textChanged.connect(lambda: self.update_dataspace_notes(self.plainTextEdit_space_notes.toPlainText()))

        # Unit button signals
        self.pushButton_milliA.clicked.connect(lambda: self.set_current_unit("mA"))
        self.pushButton_microA.clicked.connect(lambda: self.set_current_unit("µA"))
        self.pushButton_nanoA.clicked.connect(lambda: self.set_current_unit("nA"))
        self.pushButton_millimol.clicked.connect(lambda: self.set_concentration_unit("mmol"))
        self.pushButton_micromol.clicked.connect(lambda: self.set_concentration_unit("µmol"))
        self.pushButton_nanomol.clicked.connect(lambda: self.set_concentration_unit("nmol"))

        # Initialize unit buttons
        self.set_current_unit("mA")
        self.set_concentration_unit("mmol")

        # Matplotlib navigation toolbar
        navigation_toolbar = NavigationToolbar(self.canvas, self)
        self.horizontalLayout_toolbox.addWidget(navigation_toolbar)
        
        self.layout_datasets = QVBoxLayout(self.scrollAreaWidgetContents_datasets)
        self.layout_dataspaces = QVBoxLayout(self.scrollAreaWidgetContents_dataspaces)

        # Initialize one dataspace
        self.add_dataspace_widget(initialize_dataset=True)
        
        # Reset focus
        self.setFocus()

        #QApplication.processEvents()
        self.rt = RepeatedTimer(60, lambda: self.on_save_clicked(False, "autosave")) # it auto-starts, no need of rt.start()


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


    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Confirmation', 
            "Are you sure you want to quit?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.rt.stop()
            event.accept()  # Allow the window to close
        else:
            event.ignore()  # Ignore the close event


    def set_concentration_unit(self, unit: str):
        # Reset stylesheet on all buttons
        self.pushButton_millimol.setStyleSheet("background-color: rgba(128, 128, 128, 0.3)")
        self.pushButton_micromol.setStyleSheet("background-color: rgba(128, 128, 128, 0.3)")
        self.pushButton_nanomol.setStyleSheet("background-color: rgba(128, 128, 128, 0.3)")

        # Set stylesheet on clicked button
        if unit == "mmol":
            self.pushButton_millimol.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")
        elif unit == "µmol":
            self.pushButton_micromol.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")
        elif unit == "nmol":
            self.pushButton_nanomol.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")
        
        self.canvas.unit_concentration = unit
        self.canvas.update_plot_units()


    def set_current_unit(self, unit: str):
        # Reset stylesheet on all buttons
        self.pushButton_milliA.setStyleSheet("background-color: rgba(128, 128, 128, 0.3)")
        self.pushButton_microA.setStyleSheet("background-color: rgba(128, 128, 128, 0.3)")
        self.pushButton_nanoA.setStyleSheet("background-color: rgba(128, 128, 128, 0.3)")

        # Set stylesheet on clicked button
        if unit == "mA":
            self.pushButton_milliA.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")
        elif unit == "µA":
            self.pushButton_microA.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")
        elif unit == "nA":
            self.pushButton_nanoA.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")
        
        self.canvas.unit_current = unit
        self.canvas.update_plot_units()


    def on_save_clicked(self, ask_for_file_location: bool, file_name = None):
        if file_name == None:
            current_datetime = datetime.now()
            file_name = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        
        if ask_for_file_location:
            filepath, _ = QFileDialog.getSaveFileName(self, "Save File", file_name, "Pickle Files (*.pickle)")
        else:
            # Get the current working directory
            folder = os.getcwd()
            
            # Generate the file name based on current date and time
            filepath = os.path.join(folder, f"{file_name}.pickle")

        if not filepath:
            return
        
        # Add all pickleable objects to a dict
        data = {
            "window": {
                "space_widget_id": self.space_widget_id,
                "set_widget_id": self.set_widget_id,
                "current_convert_value": self.lineEdit_convert_current.text()
                #"active_spaces_ids": self.canvas.active_spaces_ids
                #"layout_datasets": self.layout_datasets,
                #"widgets": self.widgets
            },
            "plot": {
                "show_debug_info": self.canvas.show_debug_info,
                "show_legend": self.canvas.show_legend,
                "show_equation": self.canvas.show_equation,
                #"span": self.canvas.span,
                "span_initialized": self.canvas.span_initialized,
                "selected_space_id": self.canvas.selected_space_id,
                "active_spaces_ids": self.canvas.active_spaces_ids,
                "dataspaces": self.canvas.dataspaces,
                "color_index": self.canvas.color_index,
                "unit_current": self.canvas.unit_current,
                "unit_concentration": self.canvas.unit_concentration
            }
        }

        # Use pickle to write the dict into a file
        try:
            with open(filepath, "wb") as file:
                pickle.dump(data, file)
            print("File saved at:", filepath)
        except Exception as e:
            print(f"on_save_clicked: {e}")


    def on_load_clicked(self, ask_for_file_location: bool):
        if ask_for_file_location:
            filepath, _ = QFileDialog.getOpenFileName(self, "Load File", "", "Pickle Files (*.pickle)")
            if not filepath:
                return
        else:          
            # Try loading from autosave   
            folder = os.getcwd()
            filepath = os.path.join(folder, "autosave.pickle")
            if not os.path.exists(filepath):
                return

        # Delete currents widgets  
        space_ids = list(self.widgets.keys())
        if space_ids:
            for space_id in space_ids:
                self.on_dataspace_remove_clicked(space_id)

        # Read pickled data
        try:
            with open(filepath, "rb") as file:
                data = pickle.load(file)

            space_widget_id = data["window"]["space_widget_id"]
            set_widget_id = data["window"]["set_widget_id"]
            #toggled_on_space_ids = data["window"]["toggled_on_space_ids"]

            self.canvas.show_debug_info = data["plot"]["show_debug_info"]
            self.canvas.show_legend = data["plot"]["show_legend"]
            self.canvas.show_equation = data["plot"]["show_equation"]
            #self.canvas.span_initialized = data["plot"]["span_initialized"]
            selected_space_id = data["plot"]["selected_space_id"]
            active_spaces_ids = data["plot"]["active_spaces_ids"]
            dataspaces = data["plot"]["dataspaces"]
            self.canvas.color_index = data["plot"]["color_index"]
            #self.canvas.unit_current = data["plot"]["unit_current"]
            #self.canvas.unit_concentration = data["plot"]["unit_concentration"]

            # Reconstruct data and gui
            for space_id, dataspace in dataspaces.items():
                space_name = dataspace["name"]
                space_notes = dataspace["notes"]
                if space_id in active_spaces_ids:
                    space_toggled_on = True
                else:
                    space_toggled_on = False

                self.add_dataspace_widget(
                    space_id=space_id, 
                    space_name=space_name, 
                    space_notes=space_notes, 
                    initialize_dataset=False, 
                    space_toggled_on=space_toggled_on
                )
                self.canvas.set_selected_space_id(space_id, update_plot=False)

                for set_id, dataset in dataspace["datasets"].items(): ######
                    set_name = dataset["name"]
                    times = dataset["times"]
                    currents = dataset["currents"]
                    concentration = dataset["concentration"]
                    notes = dataset["notes"]
                    hidden = dataset["hidden"]
                    color = dataset["line_color"]

                    _ = self.add_dataset_widget(
                        name=set_name, 
                        concentration=concentration, 
                        notes=notes, 
                        set_id=set_id, 
                        space_id=space_id, 
                        dataset_hidden=hidden
                    )
                    self.canvas.add_dataset(
                        set_id=set_id, 
                        set_name=set_name, 
                        space_name=space_name,
                        space_notes=space_notes,
                        times=times, 
                        currents=currents, 
                        concentration=concentration, 
                        notes=notes, update_plot=False, 
                        space_id=space_id, 
                        hidden=hidden, 
                        color=color
                    )

            self.space_widget_id = space_widget_id
            self.set_widget_id = set_widget_id
            self.canvas.span_initialized = False

            self.lineEdit_convert_current.setText(data["window"]["current_convert_value"])
            self.actionDebug_Info.setChecked(self.canvas.show_debug_info)
            self.actionLegend.setChecked(self.canvas.show_legend)
            self.actionEquation.setChecked(self.canvas.show_equation)

            self.switch_dataspace(selected_space_id)
            self.set_active_dataspaces()

            self.set_current_unit(data["plot"]["unit_current"])
            self.set_concentration_unit(data["plot"]["unit_concentration"])

            self.canvas.draw_plot()        

            print("File loaded from:", filepath)
        except Exception as e:
            print(f"An error occurred while loading: {e}")
            traceback.print_exc()


    def find_concentration_from_current(self, current):
        try:
            current = float(current)
        except ValueError:
            self.lineEdit_convert_concentration.setText("")
            return
        
        datasets = self.canvas.get_datasets()
        if datasets == None:
            self.lineEdit_convert_concentration.setText("Out Of Range")
            return
        
        try:
            result = self.canvas.calculate_results(datasets)
            if len(result) < 2:
                self.lineEdit_convert_concentration.setText("Out Of Range")
                return
            
            concentrations, calculated_currents = zip(*result)
            avg_currents, _ = zip(*calculated_currents) 
            _, _, _, trendline = self.canvas.calculate_trendline(concentrations, avg_currents)
            #print(trendline)     
        except Exception as e:
            print(e)
            traceback.print_exc()
            return

        # Reverse the arrays if average currents are decreasing
        if avg_currents[0] > avg_currents[-1]:
            trendline = trendline[::-1]
            concentrations = concentrations[::-1]

        # Interpolate to find concentration corresponding to current
        concentration = np.interp(current, trendline, concentrations)
        if current < min(trendline) or current > max(trendline):
            concentration_text = "Out Of Range"
        else:
            concentration_text = str(round(concentration, 5))

        print("Min concentration:", min(concentrations))
        print("Max concentration:", max(concentrations))
        print("Interpolated concentration:", concentration)

        # Update widget
        self.lineEdit_convert_concentration.setText(concentration_text)


    def add_dataspace_widget(self, space_id = None, space_name = None, space_notes = "", initialize_dataset = True, space_toggled_on = True):
        if space_id == None:
            space_id = self.space_widget_id
            self.space_widget_id += 1
        if space_name == None:
            space_name = f"Set {space_id}"

        checkbox_toggle_space = QCheckBox(self)
        checkbox_toggle_space.setChecked(space_toggled_on)
        checkbox_toggle_space.stateChanged.connect(lambda: self.set_active_dataspaces())
        #checkbox_toggle_space.setFixedHeight(15)

        button_space = EditableButton(space_name, self)
        button_space.clicked.connect(lambda: self.switch_dataspace(space_id))
        button_space.btnTextEditingFinished.connect(lambda text: self.canvas.rename_dataspace(space_id, text))
        button_space.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")
        button_space.setFixedHeight(28)
        button_space.setFixedWidth(160)

        hbox = QHBoxLayout()
        hbox.addWidget(checkbox_toggle_space)
        hbox.addWidget(button_space)
        hbox.setContentsMargins(0, 0, 0, 0)

        self.layout_dataspaces.addLayout(hbox)
        self.layout_dataspaces.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        #self.verticalLayout_dataspaces.setContentsMargins(0, 0, 0, 0)
        #self.verticalLayout_dataspaces.setSpacing(0)

        # Store references to the widgets for later access
        self.widgets[space_id] = { 
            "dataspace_widgets": {
                "checkbox_toggle": checkbox_toggle_space,
                "button_space": button_space
            },
            "dataset_widgets": {}
        }

        # Initialize every space with one dataset
        if initialize_dataset:   
            self.switch_dataspace(space_id)
            set_id = self.add_dataset_widget()
            set_name, concentration, notes = self.get_widgets_text(set_id)
            times = np.arange(0, 100.1, 0.1)
            currents = np.linspace(-15, -5, len(times))
            self.set_active_dataspaces()
            self.canvas.add_dataset(set_id, set_name, space_name, space_notes, times, currents, concentration, notes, space_id=space_id)
            self.plainTextEdit_space_notes.setPlainText(space_notes)

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

        # Update current to concentration widgets
        self.find_concentration_from_current(self.lineEdit_convert_current.text())

        # Show dataset widgets that are in current dataspace only
        #dataset_widgets = self.widgets[space_id]["dataset_widgets"]
        for widgets in self.widgets.values(): 
            for dataset_widgets in widgets["dataset_widgets"].values():
                for dataset_widget in dataset_widgets.values():
                    dataset_widget.hide()  
        for dataset_widgets in self.widgets[space_id]["dataset_widgets"].values():
            for dataset_widget in dataset_widgets.values():
                dataset_widget.show()
        
        # Update notes text box
        if space_id in self.canvas.dataspaces:
            text = self.canvas.dataspaces[space_id]["notes"]
            self.plainTextEdit_space_notes.setPlainText(text)


    def on_dataspace_remove_clicked(self, space_id = None):
        if len(self.widgets) == 0:
            return
        
        # Delete all dataspace widgets
        if space_id == None:
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
        self.canvas.delete_dataspace(space_id)
        # Switch to first dataspace in the dict
        if len(self.widgets) > 0:
            first_id = list(self.widgets.keys())[0]
            self.switch_dataspace(first_id)


    def on_dataspace_rename_clicked(self):
        space_id = self.canvas.selected_space_id
        if space_id in self.widgets:
            button_space: EditableButton = self.widgets[space_id]["dataspace_widgets"]["button_space"]
            button_space.start_editing()

    def set_active_dataspaces(self):
        checked_space_ids = []
        # Get ids of all checked boxes
        for space_id, widgets in self.widgets.items():
            if widgets["dataspace_widgets"]["checkbox_toggle"].isChecked():
                checked_space_ids.append(space_id)

        self.canvas.set_active_spaces_ids(checked_space_ids)


    def update_dataspace_notes(self, text):
        space_id = self.canvas.selected_space_id
        self.canvas.dataspaces[space_id]["notes"] = text
    

    def add_dataset_widget(self, name = None, concentration = 0, notes = "", set_id = None, space_id = None, dataset_hidden = False):
        if set_id == None:
            set_id = self.set_widget_id
            self.set_widget_id += 1
        if space_id == None: 
            space_id = self.canvas.selected_space_id

        print(space_id)
        
        line_edit_name = QLineEdit(self)
        if name == None:
            line_edit_name.setText(f"Data {set_id}")
        else: 
            line_edit_name.setText(name)
        line_edit_name.setFixedWidth(100)
        line_edit_concentration = CustomQLineEdit(str(concentration), self)
        line_edit_concentration.setFixedWidth(50)
        line_edit_notes = QLineEdit(notes, self)

        if dataset_hidden:
            line_edit_name.setEnabled(False)
            line_edit_concentration.setEnabled(False)
            line_edit_notes.setEnabled(False)

        # Update dataset on text edited
        line_edit_name.editingFinished.connect(lambda: self.update_dataset_info(set_id))
        line_edit_concentration.textEdited.connect(lambda: self.update_dataset_info(set_id))
        line_edit_notes.editingFinished.connect(lambda: self.update_dataset_info(set_id, False))
      
        checkbox_toggle_active = QCheckBox(self)
        if dataset_hidden:
            checkbox_toggle_active.setChecked(False)
        else:
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

        # Add hbox to parent layout
        self.layout_datasets.addLayout(hbox)
        self.layout_datasets.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Store references to the widgets for later access
        dataset_widget = {
            "checkbox_toggle": checkbox_toggle_active,
            "line_edit_name": line_edit_name,
            "line_edit_concentration": line_edit_concentration,
            "line_edit_notes": line_edit_notes#,
            #"button_paste": button_paste
        }

        if not space_id in self.widgets:
            space_id = self.add_dataspace_widget(initialize_dataset=False)
        self.widgets[space_id]["dataset_widgets"][set_id] = dataset_widget

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
        dataset = self.canvas.dataspaces[space_id]["datasets"][set_id]
        dataset["hidden"] = not dataset["hidden"]
        self.canvas.draw_plot()
        
        #if widget.isEnabled():
        #    self.canvas.unhide_dataset(set_id)
        #else:
        #    self.canvas.hide_dataset(set_id)

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


    def update_dataset_info(self, id, update_plot = True):
        name, concentration, notes = self.get_widgets_text(id)
        if self.concentration_input_is_valid(id, concentration):
            self.canvas.update_dataset(id, name, concentration, notes, update_plot)
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
                self.canvas.delete_dataspace()
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
            self.canvas.add_dataset(set_id, set_name, "DATASPACE 0", "", times, currents, concentration, notes, update_plot=False)
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
    

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()


class CustomQLineEdit(QLineEdit):
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selectAll()


class EditableButton(QPushButton):
    btnTextEditingFinished = pyqtSignal(str)

    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setCheckable(False)
        self.line_edit = None
        self.currently_editing = False
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        # Start editing on double click
        if obj == self and event.type() == event.Type.MouseButtonDblClick:
            self.start_editing()
            return True
        # Finish editing if line edit loses focus without the text changing
        elif obj == self.line_edit and event.type() == event.Type.FocusOut:
            self.finish_editing()
            return True
        return super().eventFilter(obj, event)

    def start_editing(self):      
        if self.currently_editing:
            return
        
        self.currently_editing = True
        self.setStyleSheet("")
        self.old_text = self.text()

        # Create line edit on top of the button
        self.line_edit = QLineEdit(self.old_text, self)
        self.line_edit.selectAll()
        self.line_edit.setFocus()
        self.line_edit.editingFinished.connect(self.finish_editing)
        #self.line_edit.textChanged.connect(self.textChanged.emit)
        self.line_edit.setGeometry(self.rect())
        self.line_edit.show()
        self.line_edit.installEventFilter(self)

    def finish_editing(self):
        if not self.currently_editing:
            return
        
        self.currently_editing = False
        # Set button text to edited text
        new_text = self.line_edit.text()
        self.setText(new_text)

        self.btnTextEditingFinished.emit(new_text)

        # Delete line edit and reset stylesheet on button
        self.line_edit.deleteLater()
        self.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")


class PlotCanvas(FigureCanvas):
    # For type hints
    figure: plt.Figure
    axes1: Axes
    axes2: Axes

    # User toggleable info
    show_debug_info = False
    show_legend = True
    show_equation = True
    show_data = False
    show_results = True

    equation_textboxes = []
    plot_legend = None

    span = None
    span_initialized = False

    selected_space_id = 0 # Datasets within this space are drawn on the data plot
    active_spaces_ids = [0] # Results within these spaces are drawn on the results plot

    color_index = 0
    colors = []

    unit_current = "mA"
    unit_concentration = "mmol"

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


    def __init__(self, parent=None): 
        self.figure, (self.axes1, self.axes2) = plt.subplots(1, 2)
        super().__init__(self.figure)
        self.setParent(parent)
        #self.figure.tight_layout()

        # Create color table
        tableau_colors = mcolors.TABLEAU_COLORS
        css4_colors = mcolors.CSS4_COLORS
        self.colors = list(tableau_colors.values()) + list(css4_colors.values())

        self.textbox_pick_cid = self.mpl_connect("pick_event", self.on_pick)
     

    def set_selected_space_id(self, space_id: int, update_plot = True):
        self.selected_space_id = space_id
        print(f"selected space: {self.selected_space_id}")
        if update_plot:
            self.draw_plot()


    def set_active_spaces_ids(self, space_ids: list, update_plot = True):
        self.active_spaces_ids = space_ids
        print(f"active spaces: {self.active_spaces_ids}")
        if update_plot:
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
        datasets = self.get_datasets()
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


    def update_dataset(self, set_id, name, concentration, notes, update_plot = True):
        datasets = self.get_datasets()
        if set_id in datasets:
            # Update concentration and notes for the specified dataset
            datasets[set_id]['name'] = name
            datasets[set_id]['concentration'] = float(concentration)
            datasets[set_id]['notes'] = notes

            if update_plot:
                self.draw_plot()
            print(datasets[set_id]["name"])
        else:
            print(f"update_dataset: Dataset with id '{set_id}' does not exist.")


    def add_dataset(self, set_id, set_name, space_name, space_notes, times, currents, concentration, notes, update_plot = True, space_id = None, hidden = False, color = None):
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

        if not self.span_initialized: 
            self.initialize_span(times)
        if update_plot:
            self.draw_plot()

        print(self.dataspaces[self.selected_space_id]["name"])


    def get_datasets(self, space_id: int = None):
        # If no id provided, get datasets in currently selected space
        if space_id == None:
            space_id = self.selected_space_id

        if space_id in self.dataspaces:
            datasets = self.dataspaces[space_id]["datasets"]
            return datasets    
        else:
            return None
    
 
    def get_datasets_in_active_dataspaces(self):      
        active_datasets = [self.dataspaces[active_id]["datasets"] for active_id in self.active_spaces_ids if active_id in self.dataspaces]
        return active_datasets
        

    def delete_dataset(self, dataset_id):
        pass
    

    def delete_dataspace(self, space_id = None):
        # If no id provided, delete currently selected space
        if space_id == None:
            space_id = self.selected_space_id
        #print(self.dataspaces.keys())
        #print(space_id)
        if not space_id in self.dataspaces:
            return
            
        self.dataspaces.pop(space_id)
        self.span_initialized = False
        self.draw_plot()

    
    def rename_dataspace(self, space_id, name):
        print(space_id) 
        # Rename
        if space_id in self.dataspaces:
            self.dataspaces[space_id]["name"] = name
        
        # Redraw
        labels = [self.dataspaces[space_id]["name"] for space_id in self.active_spaces_ids if space_id in self.dataspaces]
        print(labels)
        if self.show_legend:
            self.axes2.legend(labels)
        self.draw()


    def initialize_span(self, times):  
        self.create_span_selector(np.array(times)) # Time values from first dataset
        last_value = times[-1]
        span_right = last_value
        span_left = round(float(last_value) * 0.9, ndigits=1)
        self.span.extents = (span_left, span_right)
        self.span_initialized = True
        

    def plot_results(self): 
        #if not self.show_results:
        #    self.axes2.set_visible(False)
        #    return
        #self.axes2.set_visible(True)

        active_datasets = self.get_datasets_in_active_dataspaces()
        if len(active_datasets) == 0:
            info_text = "No sets enabled"
            self.display_results_info_text(info_text)
            return
   
        results = []
        for dataset in active_datasets:
            result = self.calculate_results(dataset)
            results.append(result)

        self.axes2.clear()
        tableau_colors = list(mcolors.TABLEAU_COLORS)
        labels = [self.dataspaces[space_id]["name"] for space_id in self.active_spaces_ids if space_id in self.dataspaces] # active_datasets or results dont have dataspace names. fix later

        self.equation_textboxes = []

        for i, result in enumerate(results):
            if result == None:
                return
            
            if len(result) < 2:
                info_text = f"Add atleast 2 different concentrations \n to \"{labels[i]}\""
                self.display_results_info_text(info_text)
                return
            
            # Unpack data
            concentrations, calculated_currents = zip(*result)
            avg_currents, std_currents = zip(*calculated_currents)

            # Calculate trendline
            slope, intercept, r_squared, trendline = self.calculate_trendline(concentrations, avg_currents)

            # Plot the data
            self.axes2.errorbar(concentrations, avg_currents, yerr=std_currents, marker="o", capsize=3, label=labels[i], color=tableau_colors[i])
            self.axes2.plot(concentrations, trendline, linestyle="--", color=tableau_colors[i])

            # Display the equation
            if self.show_equation:
                equation_text = f"y = {slope:.4f}x + {intercept:.4f}"
                r_squared_text = f"R² = {r_squared:.6f}"
                text_x = 0.05
                text_y = i / (self.height() * 0.02) + 0.07
                equation_textbox = self.axes2.text(
                    text_x, text_y, 
                    f"{equation_text}\n{r_squared_text}", 
                    fontsize=9, 
                    bbox=dict(facecolor=tableau_colors[i], alpha=0.3), 
                    horizontalalignment="left", verticalalignment="center", 
                    transform=self.axes2.transAxes,
                    picker=True
                )
                # Save text boxes for repositioning them later
                self.equation_textboxes.append(equation_textbox)

        # Set legend, grid, title, labels 
        if self.show_legend:
            self.axes2.legend(fontsize=9)
        self.axes2.grid(True)
        self.axes2.set_title("Results")
        self.axes2.set_ylabel(f"current({self.unit_current})")
        self.axes2.set_xlabel(f"concentration({self.unit_concentration})")
        
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
    

    def display_results_info_text(self, text):
        self.axes2.clear()
        self.axes2.set_title("Results")
        self.axes2.set_ylabel(f"current({self.unit_current})")
        self.axes2.set_xlabel(f"concentration({self.unit_concentration})")
        self.axes2.text(0.5, 0.5, text, fontsize=10, horizontalalignment="center", verticalalignment="center", transform=self.axes2.transAxes)

    def calculate_trendline(self, x, y):
        # Perform linear regression to get slope, intercept, and R-squared
        slope, intercept = np.polyfit(x, y, 1)
        r_squared = np.corrcoef(x, y)[0, 1]**2
        trendline = slope * np.array(x) + intercept

        return slope, intercept, r_squared, trendline


    def calculate_results(self, datasets):
        # Iterate over each dataset
        concentration_data = {}
        for data in datasets.values():
            if data["hidden"]:
                continue
            
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
        #if not self.show_data:
        #   self.axes1.set_visible(False)
        #   self.axes1.set_axis_off()
        #   self.figure.delaxes(self.axes1)
        #    return
        #self.axes1.set_visible(True)

        # Clear existing plot
        self.axes1.clear()

        datasets = self.get_datasets()
        if datasets == None:
            self.axes1.grid(True)
            self.draw()
            #print("no datasets")
            return
        
        # Plot each dataset      
        for data in datasets.values():
            if data["hidden"]:
                continue

            times = data['times']
            currents = data['currents']
            name = data['name']
            line_color = data['line_color']
            self.axes1.plot(times, currents, label=name, color=line_color)
        
        if self.show_legend:
            self.update_legend()

        # Set grid, labels, title
        self.axes1.grid(True)
        self.axes1.set_title(self.dataspaces[self.selected_space_id]["name"])
        self.axes1.set_ylabel(f"current({self.unit_current})")
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
        
    
    def update_plot_units(self):
        self.axes1.set_ylabel(f"current({self.unit_current})")
        self.axes2.set_ylabel(f"current({self.unit_current})")
        self.axes2.set_xlabel(f"concentration({self.unit_concentration})")
        self.draw()
    
    def update_legend(self):
        if not self.show_legend:
            return
        
        self.plot_legend = self.axes1.legend(loc="lower left", fontsize=9)
        legend_height = self.plot_legend.get_window_extent().max[1]
        plot_height = self.height()
        print(legend_height, plot_height)
        if legend_height > plot_height - 30:
            self.plot_legend.remove()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.equation_textboxes:     
            for i, textbox in enumerate(self.equation_textboxes):
                x = 0.05
                y = i / (self.height() * 0.02) + 0.07
                textbox.set_position((x, y))

        if self.plot_legend:
            self.update_legend()
        
        self.figure.tight_layout()

    def on_pick(self, event):
        print(event.artist)
        
        artist: plt.Text = event.artist
        text = artist.get_text()
        QApplication.clipboard().setText(text)

        old_alpha = artist.get_bbox_patch().get_alpha()

        artist.get_bbox_patch().set_alpha(0.7)
        self.draw()
        
        Timer(0.05, lambda: self.reset_textbox_alpha(artist, old_alpha)).start()

    def reset_textbox_alpha(self, textbox: plt.Text, old_alpha):
        textbox.get_bbox_patch().set_alpha(old_alpha)
        self.draw()
            

def main():
    app = QApplication(sys.argv)
    window = MyMainWindow()
    window.setWindowTitle("Amp Analyzer")
    window.show()
    #app.processEvents()  
    window.on_load_clicked(ask_for_file_location=False)
    sys.exit(app.exec()) 


if __name__ == "__main__":
    main()
