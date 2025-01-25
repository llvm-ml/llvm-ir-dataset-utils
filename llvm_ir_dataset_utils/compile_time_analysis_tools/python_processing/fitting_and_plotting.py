"""Functions for plotting instruction counts and text segment size data.

This script contains two functions. One function makes a scatter plot of
compiler instruction counts and text segment size data. The other makes
a histogram of the compiler instruction counts.

Example Usage: from fitting_and_plotting import *
"""
import matplotlib.pyplot as plt
from read_column import csv_to_pandas_df
import numpy as np


def plot_instruction_counts_v_textseg(lang: str,
                                      storage: str,
                                      show: bool = False) -> None:
  """Display a scatter plot of the data using matplotlib pyplot.

  The function internally creates a pandas dataframe from the provided
  CSV file location. The columns pertaining to text segment size and
  compiler CPU instruction counts are plotted in a scatter plot with
  logarithmic axis. The x and y bounds of the plot are limited to
  provide a standard range of values for all plots.

  Args:
    lang: A string which represents the type of IR file data being
      accessed
    storage: A string which is the path to the IR CSV data
    show: A boolean which if set to True will print the number of data
      points and show the scatter plot using pyplot.show(), otherwise
      the plot is saved to a .pdf file
  """
  df = csv_to_pandas_df(lang, storage)
  textseg_data = df["text_segment"]
  inst_data = df["instruction"]
  c, b, a = np.polyfit(textseg_data, inst_data, 2)

  x_axis = range(min(textseg_data), max(textseg_data), 10)
  z = np.polyval([c, b, a], x_axis)

  plt.scatter(textseg_data, inst_data)
  plt.xscale("log")
  plt.yscale("log")
  plt.gca().set_ylim([10**8, 10**13])
  plt.gca().set_xlim([10**(-1), 10**9])
  plt.xlabel("Text Segment Size (bytes)")
  plt.ylabel("Compiler CPU Instructions Count")
  if (lang == "cpp"):
    plt.title("Clang++ Compiler Instructions vs. Text Segment Size (" + lang +
              ")")
  else:
    plt.title("Clang Compiler Instructions vs. Text Segment Size (" + lang +
              ")")
  plt.plot(x_axis, z, 'r')
  equation = f"${c:.1e}x^2 + {b:.1e}x + {a:.1e}$"
  plt.legend([f"fit: {equation}", "original"])
  if (show):
    print(len(textseg_data))
    plt.show()
  else:
    plt.savefig(fname=lang + "_instvtext.pdf", format="pdf")
  plt.close()


def plot_instruction_counts_histograms(lang: str,
                                       storage: str,
                                       show: bool = False) -> None:
  """Display a histogram of the compile time data using matplotlib pyplot.

  The function internally creates a pandas dataframe from the provided
  CSV file location. The columns pertaining to compiler CPU instruction
  counts are plotted in a histogram with logarithmic axis. The x and y
  bounds of the plot are limited to provide a standard range of values
  for all plots.

  Args:
    lang: A string which represents the type of IR file data being
      accessed
    storage: A string which is the path to the IR CSV data
    show: A boolean which if set to True will print the number of data
      points and display the histogram using pyplot.show(), otherwise
      the plot is saved to a .pdf file
  """
  df = csv_to_pandas_df(lang, storage)
  inst_data = df["instruction"]
  plt.hist(inst_data, bins='auto', alpha=1, color='b')
  plt.title("Histogram of Compiler Instructions (" + lang + ")")
  plt.xscale("log")
  plt.yscale("log")
  plt.gca().set_ylim([10**(-1), 10**5])
  plt.gca().set_xlim([10**8, 10**13])
  plt.xlabel('Compiler CPU Instructions Count')
  plt.ylabel('No. of IR Files')

  plt.text(max(inst_data), 1.1, format(max(inst_data), '.2e'), ha='center')

  if (show):
    print(len(inst_data))
    plt.show()
  else:
    plt.savefig(fname=lang + "_hist.pdf", format="pdf")
  plt.close()
