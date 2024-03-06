import pandas as pd
import matplotlib.pyplot as plt

import pandas as pd

csv_file = "testitesti.csv"

# Read the CSV file into a DataFrame
df = pd.read_csv(csv_file, encoding="utf-16", header=5)


# Plot time vs. current for each channel
for i in range(8):
    if i  == 0:
        current_column = "µA"
    else:
        current_column = f"µA.{i}"
    plt.plot(df["s"], df[current_column], label=f"Channel {i}")

# Add labels and legend
plt.xlabel("Time")
plt.ylabel("Current (µA)")
plt.title("Current vs. Time for Each Channel")
plt.legend()

axes = plt.gca()
axes.xaxis.set_major_locator(plt.MaxNLocator(10))
axes.yaxis.set_major_locator(plt.MaxNLocator(10))

# Show plot
plt.show()