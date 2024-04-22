import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.widgets import SpanSelector
from matplotlib.axes import Axes
from PyQt6.QtWidgets import QApplication
from threading import Timer
from plotting.plot_data_handler import PlotDataHandler

class PlotCanvas(FigureCanvas):
    figure: plt.Figure
    axes1: Axes
    axes2: Axes

    # User toggleable info
    show_debug_info = False
    show_legend = True
    show_equation = True

    equation_textboxes = []
    plot_legend = None

    # Time span selector
    span = None
    span_initialized = False

    unit_current = "mA"
    unit_concentration = "mmol"

    # Contains data and data operations
    data_handler: PlotDataHandler


    def __init__(self, parent=None): 
        self.figure, (self.axes1, self.axes2) = plt.subplots(1, 2)
        super().__init__(self.figure)
        self.setParent(parent)

        self.data_handler = PlotDataHandler()
        self.textbox_pick_cid = self.mpl_connect("pick_event", self.on_pick)
    
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
        self.data_handler.time_range = (vmin, vmax)
        self.draw_plot()

    def create_span_selector(self, times, extents: tuple[int, int] = None):  
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
            snap_values=times) # Snap to time values 
        
        if extents == None:
            span_right = times[-1]
            span_left = round(float(span_right) * 0.9, ndigits=1)
            self.span.extents = (span_left, span_right)   
        else:
            self.span.extents = extents
        self.span_initialized = True
        self.data_handler.time_range = self.span.extents

    def plot_data(self):
        # Clear existing plot
        self.axes1.clear()

        datasets = self.data_handler.get_datasets()
        if datasets == None:
            self.axes1.grid(True)
            self.draw()
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
        self.axes1.set_ylabel(f"current({self.unit_current})")
        self.axes1.set_xlabel("time(s)")
        space_name = self.data_handler.dataspaces[self.data_handler.selected_space_id]["name"]
        self.axes1.set_title(space_name)
        
        # Set tick locations
        self.axes1.xaxis.set_major_locator(plt.MaxNLocator(10))
        self.axes1.yaxis.set_major_locator(plt.MaxNLocator(10))

        if not self.span_initialized: 
            self.create_span_selector(times)
            print("span initialized")

    def plot_results(self): 
        active_datasets = self.data_handler.get_datasets_in_active_dataspaces()
        if len(active_datasets) == 0:
            info_text = "No sets enabled"
            self.display_results_info_text(info_text)
            return
   
        results = []
        for dataset in active_datasets:
            result = self.data_handler.calculate_results(dataset)
            results.append(result)

        self.axes2.clear()
        tableau_colors = list(mcolors.TABLEAU_COLORS)
        labels = self.data_handler.get_dataspace_names()

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
            slope, intercept, r_squared, trendline = self.data_handler.calculate_trendline(concentrations, avg_currents)

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
        
        self.axes2.xaxis.set_major_locator(plt.AutoLocator())
        self.axes2.yaxis.set_major_locator(plt.MaxNLocator(10))

        if self.show_debug_info and len(results) == 1:
            self.draw_debug_box(concentrations, avg_currents, std_currents, slope, intercept, trendline)
    
    def display_results_info_text(self, text):
        self.axes2.clear()
        self.axes2.set_title("Results")
        self.axes2.set_ylabel(f"current({self.unit_current})")
        self.axes2.set_xlabel(f"concentration({self.unit_concentration})")
        self.axes2.text(0.5, 0.5, text, fontsize=10, horizontalalignment="center", verticalalignment="center", transform=self.axes2.transAxes)

    def draw_plot(self):    
        self.plot_data()
        self.check_span_selector_snaps()
        self.plot_results()
        self.figure.tight_layout()
        self.draw()
        print(f"draw_plot called")

    def check_span_selector_snaps(self):
        smallest_times_set = self.data_handler.get_smallest_times_dataset()
        if len(smallest_times_set) == 0:
            return
        
        if smallest_times_set[-1] < self.span.snap_values[-1]:
            self.create_span_selector(smallest_times_set)

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
        # Copy equation to clipboard on click
        artist: plt.Text = event.artist
        text = artist.get_text()
        QApplication.clipboard().setText(text)

        # Flash equation box for feedback
        old_alpha = artist.get_bbox_patch().get_alpha() 
        artist.get_bbox_patch().set_alpha(0.7)
        self.draw()
        
        Timer(0.05, lambda: self.reset_textbox_alpha(artist, old_alpha)).start()

    def reset_textbox_alpha(self, textbox: plt.Text, old_alpha):
        textbox.get_bbox_patch().set_alpha(old_alpha)
        self.draw()
