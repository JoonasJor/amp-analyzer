import matplotlib.pyplot as plt
import pandas as pd
import pyperclip
from io import StringIO

def plot_data_from_clipboard():
    # Read data from clipboard
    clipboard_data = pyperclip.paste()

    # Parse clipboard data into a DataFrame
    df = pd.read_csv(StringIO(clipboard_data), sep='\t')

    # Plot the data
    plt.plot(df['time/s'], df['current/µA'], label='Current')
    
    # Set title and legend and turn on grid
    plt.title('Matplotlib Plot')
    plt.legend()
    plt.grid(True)

    # Set labels for axes
    plt.ylabel("current/µA")
    plt.xlabel("time/s")

    # Set number of ticks on the x and y axes
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(10))
    plt.gca().yaxis.set_major_locator(plt.MaxNLocator(10))

    plt.show()

# Example usage:
if __name__ == "__main__":
    plot_data_from_clipboard()
