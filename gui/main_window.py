import os
import traceback
import numpy as np
import pickle
import gui.data_operations as do
from datetime import datetime
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QLineEdit, QHBoxLayout, QMessageBox, QFileDialog, QCheckBox
from PyQt6.uic import loadUi
from PyQt6.QtCore import Qt, QFileInfo
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from plotting import plotter
from utils.repeated_timer import RepeatedTimer
from gui.custom_widgets import CustomQLineEdit, EditableButton

class MainWindow(QMainWindow):
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
        self.setAcceptDrops(True) # Enable dropping onto the main window

        self.plot = plotter.PlotCanvas(self.plotWidget)
        layout = QVBoxLayout(self.plotWidget)
        layout.addWidget(self.plot)
        layout.setContentsMargins(2, 2, 2, 2)

        # Menu button signals
        #self.actionImport_data_from_XLSX.triggered.connect(self.on_import_data_from_csv_clicked)
        #self.actionImport_data_from_CSV.triggered.connect(self.on_import_data_from_csv_clicked)
        self.actionImport_data_from_PSSESSION_PST.triggered.connect(self.on_import_data_from_pssession_pst_clicked)
        self.actionDebug_Info.triggered.connect(self.plot.toggle_debug_info)
        self.actionLegend.triggered.connect(self.plot.toggle_legend)
        self.actionEquation.triggered.connect(self.plot.toggle_equation)
        self.actionSave.triggered.connect(lambda: self.on_save_clicked(ask_for_file_location=False))
        self.actionSave_as.triggered.connect(lambda: self.on_save_clicked(ask_for_file_location=True))
        self.actionLoad.triggered.connect(lambda: self.on_load_clicked(ask_for_file_location=True))

        # Dataspace button signals
        self.pushButton_dataspace_add.clicked.connect(lambda: self.on_dataspace_add_clicked())
        self.pushButton_dataspace_remove.clicked.connect(lambda: self.remove_dataspace_widget())
        self.pushButton_dataspace_rename.clicked.connect(lambda: self.on_dataspace_rename_clicked())

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
        navigation_toolbar = NavigationToolbar(self.plot, self)
        self.horizontalLayout_toolbox.addWidget(navigation_toolbar)
        
        self.layout_datasets = QVBoxLayout(self.scrollAreaWidgetContents_datasets)
        self.layout_dataspaces = QVBoxLayout(self.scrollAreaWidgetContents_dataspaces)

        # Initialize one dataspace
        self.add_dataspace_widget(initialize_dataset=True)
        self.setFocus()

        # Save program state to file every 60s
        self.rt = RepeatedTimer(60, lambda: self.on_save_clicked(False, "autosave"))

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
                    filepaths.extend([os.path.join(root, filename) for filename in filenames if filename.endswith('.pssession') or filename.endswith('.pst')])
        if individual_files:
            filepaths.extend([file for file in individual_files if file.endswith('.pssession') or file.endswith('.pst')])

        space_id = self.plot.data_handler.selected_space_id
        if space_id not in self.plot.data_handler.dataspaces:
            self.add_dataspace_widget(space_id=space_id, initialize_dataset=False)
            self.handle_pssession_pst_data(sorted(filepaths))
        else: 
            if len(self.plot.data_handler.dataspaces[space_id]["datasets"]) > 0:
                ret = self.msg_box_overwrite(space_id)
                if ret == 1:
                    self.handle_pssession_pst_data(sorted(filepaths))
            else:
                self.handle_pssession_pst_data(sorted(filepaths))

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Confirmation', 
            "Are you sure you want to quit?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.rt.stop()
            event.accept() # Allow the window to close
        else:
            event.ignore() # Ignore the close event

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
        
        self.plot.unit_concentration = unit
        self.plot.update_plot_units()

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
        
        self.plot.unit_current = unit
        self.plot.update_plot_units()

    def on_save_clicked(self, ask_for_file_location: bool, filename = None):
        if filename == None:
            current_datetime = datetime.now()
            filename = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        
        if ask_for_file_location:
            filepath, _ = QFileDialog.getSaveFileName(self, "Save File", filename, "Pickle Files (*.pickle)")
        else:
            folder = os.getcwd()    
            filepath = os.path.join(folder, f"{filename}.pickle")
        if not filepath:
            return  
        
        # Add all pickleable objects to a dict
        data = {
            "window": {
                "space_widget_id": self.space_widget_id,
                "set_widget_id": self.set_widget_id,
                "current_convert_value": self.lineEdit_convert_current.text()
            },
            "plot": {
                "show_debug_info": self.plot.show_debug_info,
                "show_legend": self.plot.show_legend,
                "show_equation": self.plot.show_equation,
                "span_initialized": self.plot.span_initialized,
                "span_extents": self.plot.span.extents,
                "selected_space_id": self.plot.data_handler.selected_space_id,
                "active_spaces_ids": self.plot.data_handler.active_spaces_ids,
                "dataspaces": self.plot.data_handler.dataspaces,
                "color_index": self.plot.data_handler.color_index,
                "unit_current": self.plot.unit_current,
                "unit_concentration": self.plot.unit_concentration
            }
        }

        do.save_program_state_to_file(data, filepath)   

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

        # Read pickled data
        try:
            data = do.load_program_state_from_file(filepath)
            if data == None:
                return
            
            # Delete currents widgets  
            space_ids = list(self.widgets.keys())
            if space_ids:
                for space_id in space_ids:
                    self.remove_dataspace_widget(space_id)

            space_widget_id = data["window"]["space_widget_id"]
            set_widget_id = data["window"]["set_widget_id"]

            self.plot.show_debug_info = data["plot"]["show_debug_info"]
            self.plot.show_legend = data["plot"]["show_legend"]
            self.plot.show_equation = data["plot"]["show_equation"]
            selected_space_id = data["plot"]["selected_space_id"]
            active_spaces_ids = data["plot"]["active_spaces_ids"]
            dataspaces: dict = data["plot"]["dataspaces"]
            self.plot.data_handler.color_index = data["plot"]["color_index"]

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
                self.plot.data_handler.selected_space_id = space_id

                datasets: dict = dataspace["datasets"]
                for set_id, dataset in datasets.items():
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
                    self.plot.data_handler.add_dataset(
                        set_id=set_id, 
                        set_name=set_name, 
                        space_name=space_name,
                        space_notes=space_notes,
                        times=times, 
                        currents=currents, 
                        concentration=concentration, 
                        notes=notes, 
                        space_id=space_id, 
                        hidden=hidden, 
                        color=color
                    )

            self.space_widget_id = space_widget_id
            self.set_widget_id = set_widget_id

            self.lineEdit_convert_current.setText(data["window"]["current_convert_value"])
            self.actionDebug_Info.setChecked(self.plot.show_debug_info)
            self.actionLegend.setChecked(self.plot.show_legend)
            self.actionEquation.setChecked(self.plot.show_equation)

            self.switch_dataspace(selected_space_id)
            self.set_active_dataspaces()

            self.set_current_unit(data["plot"]["unit_current"])
            self.set_concentration_unit(data["plot"]["unit_concentration"])
            
            self.plot.span_initialized = data["plot"]["span_initialized"]  
            self.plot.span.extents = data["plot"]["span_extents"]
            self.plot.draw_plot()         

            print("File loaded from:", filepath)
        except Exception as e:
            print(f"An error occurred while loading: {e}")
            traceback.print_exc()

    def on_dataspace_add_clicked(self):
        self.add_dataspace_widget(initialize_dataset=True)

    def on_dataspace_remove_clicked(self):
        self.remove_dataspace_widget()

    def on_dataspace_rename_clicked(self):
        self.rename_dataspace_widget()

    def on_dataspace_button_editing_finished(self, space_id, text):
        data_handler = self.plot.data_handler
        data_handler.rename_dataspace(space_id, text)

        # Update legend
        if self.plot.show_legend:
            labels = data_handler.get_dataspace_names()
            self.plot.axes2.legend(labels)
        self.plot.draw()

    def find_concentration_from_current(self, current):
        try:
            current = float(current)
        except ValueError:
            self.lineEdit_convert_concentration.setText("")
            return
        
        datasets = self.plot.data_handler.get_datasets()
        if datasets == None:
            self.lineEdit_convert_concentration.setText("Out Of Range")
            return
        
        try:
            result = self.plot.data_handler.calculate_results(datasets)
            if len(result) < 2:
                self.lineEdit_convert_concentration.setText("Out Of Range")
                return
            
            concentrations, calculated_currents = zip(*result)
            avg_currents, _ = zip(*calculated_currents) 
            _, _, _, trendline = self.plot.data_handler.calculate_trendline(concentrations, avg_currents)   
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

        button_space = EditableButton(space_name, self)
        button_space.clicked.connect(lambda: self.switch_dataspace(space_id))
        button_space.btnTextEditingFinished.connect(lambda text: self.on_dataspace_button_editing_finished(space_id, text))
        button_space.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")
        button_space.setFixedHeight(28)
        button_space.setFixedWidth(160)

        hbox = QHBoxLayout()
        hbox.addWidget(checkbox_toggle_space)
        hbox.addWidget(button_space)
        hbox.setContentsMargins(0, 0, 0, 0)

        self.layout_dataspaces.addLayout(hbox)
        self.layout_dataspaces.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Store references to the widgets for later access
        self.widgets[space_id] = { 
            "dataspace_name": space_name,
            "dataspace_widgets": {
                "checkbox_toggle": checkbox_toggle_space,
                "button_space": button_space
            },
            "dataset_widgets": {}
        }

        if initialize_dataset:   
            self.switch_dataspace(space_id)
            set_id = self.add_dataset_widget()
            _, set_name, concentration, notes = self.get_widgets_text(set_id)
            times = np.arange(0, 100.1, 0.1)
            currents = np.linspace(-15, -5, len(times))
            self.set_active_dataspaces()
            self.plot.data_handler.add_dataset(set_id, set_name, space_name, space_notes, times, currents, concentration, notes, space_id=space_id)
            self.plainTextEdit_space_notes.setPlainText(space_notes)
            self.plot.draw_plot()

        return space_id

    def remove_dataspace_widget(self, space_id = None):
        if len(self.widgets) == 0:
            return
        
        # Delete all dataspace widgets
        if space_id == None:
            space_id = self.plot.data_handler.selected_space_id
        dataspace_widgets: dict = self.widgets[space_id]["dataspace_widgets"]
        for widget in dataspace_widgets.values():
            widget.deleteLater()

        # Delete all dataset widgets within current dataspace
        dataset_widgets: dict = self.widgets[space_id]["dataset_widgets"]
        for dataset_widget in dataset_widgets.values():
            for widget in dataset_widget.values():
                widget.deleteLater()

        # Remove dictionary entry
        self.widgets.pop(space_id)
        # Delete all data within current dataspace
        self.plot.data_handler.delete_dataspace(space_id)
        self.plot.draw_plot()
        # Switch to first dataspace in the dict
        if len(self.widgets) > 0:
            first_id = list(self.widgets.keys())[0]
            self.switch_dataspace(first_id)     

    def rename_dataspace_widget(self):
        space_id = self.plot.data_handler.selected_space_id
        if space_id in self.widgets:
            button_space: EditableButton = self.widgets[space_id]["dataspace_widgets"]["button_space"]
            button_space.start_editing()

    def switch_dataspace(self, space_id):
        # Get all dataspace buttons across all dataspaces
        dataspace_buttons = [widgets["dataspace_widgets"]["button_space"] for widgets in self.widgets.values()]
        # Reset stylesheet on all buttons
        for button in dataspace_buttons:
            button.setStyleSheet("background-color: rgba(128, 128, 128, 0.3)")

        # Set stylesheet on clicked button
        self.widgets[space_id]["dataspace_widgets"]["button_space"].setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")

        # Update dataspace id in plot
        self.plot.data_handler.selected_space_id = space_id
        self.plot.draw_plot()

        # Update current to concentration widgets
        self.find_concentration_from_current(self.lineEdit_convert_current.text())

        # Show dataset widgets that are in current dataspace only
        for widgets in self.widgets.values(): 
            for dataset_widgets in widgets["dataset_widgets"].values():
                for dataset_widget in dataset_widgets.values():
                    dataset_widget.hide()  
        for dataset_widgets in self.widgets[space_id]["dataset_widgets"].values():
            for dataset_widget in dataset_widgets.values():
                dataset_widget.show()
        
        # Update notes text box
        dataspaces = self.plot.data_handler.dataspaces
        if space_id in dataspaces:
            text = dataspaces[space_id]["notes"]
            self.plainTextEdit_space_notes.setPlainText(text)

    def set_active_dataspaces(self):
        checked_space_ids = []
        # Get ids of all checked boxes
        for space_id, widgets in self.widgets.items():
            if widgets["dataspace_widgets"]["checkbox_toggle"].isChecked():
                checked_space_ids.append(space_id)

        self.plot.data_handler.active_spaces_ids = checked_space_ids
        self.plot.draw_plot()

    def update_dataspace_notes(self, text):
        data_handler = self.plot.data_handler
        space_id = data_handler.selected_space_id
        data_handler.dataspaces[space_id]["notes"] = text
    
    def add_dataset_widget(self, name = None, concentration = 0, notes = "", set_id = None, space_id = None, dataset_hidden = False):
        if set_id == None:
            set_id = self.set_widget_id
            self.set_widget_id += 1
        if space_id == None: 
            space_id = self.plot.data_handler.selected_space_id
        
        line_edit_name = QLineEdit(self)
        if name == None:
            line_edit_name.setText(f"Data {set_id}")
        else: 
            line_edit_name.setText(name)
        line_edit_name.setFixedWidth(100)
        line_edit_concentration = CustomQLineEdit(space_id, str(concentration), self)
        line_edit_concentration.setFixedWidth(50)
        line_edit_notes = QLineEdit(notes, self)

        if dataset_hidden:
            line_edit_name.setEnabled(False)
            line_edit_concentration.setEnabled(False)
            line_edit_notes.setEnabled(False)

        # Update dataset on text edited
        line_edit_name.editingFinished.connect(lambda: self.on_dataset_text_edited(set_id))
        line_edit_concentration.textChanged.connect(lambda: self.on_dataset_text_edited(set_id))
        line_edit_notes.editingFinished.connect(lambda: self.on_dataset_text_edited(set_id, False))
      
        checkbox_toggle_active = QCheckBox(self)
        if dataset_hidden:
            checkbox_toggle_active.setChecked(False)
        else:
            checkbox_toggle_active.setChecked(True)
        checkbox_toggle_active.stateChanged.connect(lambda: self.toggle_dataset(set_id))

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
            "line_edit_notes": line_edit_notes
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
            dataset_widget: dict = widgets["dataset_widgets"][set_id]
            for widget in dataset_widget.values():
                widget.deleteLater()
            # Remove dictionary entry
            widgets["dataset_widgets"].pop(set_id)          

    def toggle_dataset(self, set_id: int):
        space_id = self.plot.data_handler.selected_space_id
        if set_id not in self.widgets[space_id]["dataset_widgets"]:
            print(f"toggle_dataset: Dataset with ID {set_id} does not exist.")
            return
              
        # Toggle widgets
        dataset_widget: dict = self.widgets[space_id]["dataset_widgets"][set_id]
        for key, widget in dataset_widget.items():
            if key != "checkbox_toggle": # Do not toggle the checkbox itself
                widget.setEnabled(not widget.isEnabled())

        # Toggle dataset
        dataset = self.plot.data_handler.dataspaces[space_id]["datasets"][set_id]
        dataset["hidden"] = not dataset["hidden"]
        self.plot.draw_plot()

        self.setFocus() # Prevent setting focus to next widget

    def concentration_input_is_valid(self, set_id, input):
        space_id = self.plot.data_handler.selected_space_id
        concentration_widget = self.widgets[space_id]["dataset_widgets"][set_id]["line_edit_concentration"]
        # Check if input is numeric
        try:
            float(input)    
            concentration_widget.setStyleSheet("")
            return True
        except ValueError:
            concentration_widget.setStyleSheet("background-color: rgba(140, 0, 0, 0.3)")
            return False

    def on_dataset_text_edited(self, id, update_plot = True):
        _, name, concentration, notes = self.get_widgets_text(id)
        if self.concentration_input_is_valid(id, concentration):
            self.plot.data_handler.update_dataset(id, name, concentration, notes)
            if update_plot:
                self.plot.draw_plot()

    def get_widgets_text(self, set_id):
        space_id = self.plot.data_handler.selected_space_id
        space_name = self.widgets[space_id]["dataspace_name"]
        dataset_widgets = self.widgets[space_id]["dataset_widgets"][set_id]
        set_name = dataset_widgets["line_edit_name"].text()
        concentration = dataset_widgets["line_edit_concentration"].text()
        notes = dataset_widgets["line_edit_notes"].text()
        return space_name, set_name, concentration, notes

    def on_import_data_from_csv_clicked(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("CSVs (*.csv)")
        if not dialog.exec():
            return
        # Todo

    def on_import_data_from_pssession_pst_clicked(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilters(["PSSESSION (*.pssession)", "PST (*.pst)"])
        if not dialog.exec():
            return
        
        filepaths = dialog.selectedFiles()
        print("Selected file:", filepaths)

        data_handler = self.plot.data_handler
        space_id = data_handler.selected_space_id
        if space_id not in data_handler.dataspaces:
            self.add_dataspace_widget(space_id=space_id, initialize_dataset=False)
        else: 
            if len(data_handler.dataspaces[space_id]["datasets"]) > 0:
                ret = self.msg_box_overwrite(space_id)
                if ret == 1:
                    self.handle_pssession_pst_data(sorted(filepaths))
            else:
                self.handle_pssession_pst_data(sorted(filepaths))

    def handle_pssession_pst_data(self, filepaths):
        for filepath in filepaths:
            times, currents, set_name = do.extract_pssession_pst_data_from_file(filepath)
            set_id = self.add_dataset_widget(set_name)
            dataspace_name, _, concentration, notes = self.get_widgets_text(set_id)
            self.plot.data_handler.add_dataset(set_id, set_name, dataspace_name, "", times, currents, concentration, notes)
        self.plot.draw_plot()

    def msg_box_overwrite(self, space_id):
            msgBox = QMessageBox()
            msgBox.setWindowTitle("Dataset Exists")
            msgBox.setText("Overwrite existing dataset?")
            msgBox.setStandardButtons(QMessageBox.StandardButton.Yes | 
                                    QMessageBox.StandardButton.No | 
                                    QMessageBox.StandardButton.Cancel)
            ret = msgBox.exec()

            if ret == QMessageBox.StandardButton.Cancel:
                # Cancel action
                return 0
            elif ret == QMessageBox.StandardButton.Yes:
                # Delete widgets
                set_ids = list(self.widgets[space_id]["dataset_widgets"].keys())
                for set_id in set_ids:
                    self.delete_dataset_widget(set_id)
                    
                # Delete all datasets within current dataspace
                data_handler = self.plot.data_handler
                space_id = data_handler.selected_space_id
                data_handler.dataspaces[space_id]["datasets"] = {}
                return 1
            elif ret == QMessageBox.StandardButton.No:
                return 1
   