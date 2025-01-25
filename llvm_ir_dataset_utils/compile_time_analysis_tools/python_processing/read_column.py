"""Functions to create a dataframe from a CSV and extract the outlying rows.

The functions in this script can be used to create a Pandas dataframe
for the CSV data extracted from the IR dataset and analyze it. Using a
simple outlier extraction method, rows which constitute file data can be
chosen on a basis which finds IR files to be outliers.

Example usage: from read_column import *
"""
import pandas as pd


def csv_to_pandas_df(lang: str,
                     storage: str,
                     file_name_suffix: str = 'combined.csv'):
  """Creates a Pandas dataframe from the specified CSV file.

  Args:
    lang: A string which represents the type of IR file data being
      accessed
    storage: A string which is the path to the IR CSV data
    file_name_suffix: The suffix present on each CSV file with prefix
      as lang

  Returns: pandas.core.frame.DataFrame
  """

  df = pd.read_csv(
      storage + '/' + lang + '_' + file_name_suffix, skipinitialspace=True)
  return df


def outlier_rows(lang: str,
                 storage: str,
                 outlier_num: int = 10,
                 write_to_csv: bool = False):
  """Creates a Pandas dataframe from the specified CSV file.

  The function creates a dataframe and initially filters out half of the
  rows which do not fall into the 50th percentile for the "percentage"
  column. Then, any row which does not fall into the 75th percentile for
  the "instruction" column is filtered out. Using outlier_num, the
  largest n rows for "percentage" are returned as the outlying files
  dataframe.

  Args:
    lang: A string which represents the type of IR file data being
      accessed
    storage: A string which is the path to the IR CSV data
    outlier_num: The number of IR file outliers to display
    write_to_csv: If True, the resulting dataframe will be written to a
      CSV file
  
  Returns: pandas.core.frame.DataFrame
  """
  df = csv_to_pandas_df(lang, storage)
  outlier_df = df.nlargest(df.shape[0] // 2, "percentage")
  outlier_df = outlier_df[outlier_df.instruction > outlier_df["instruction"]
                          .quantile(q=.75, interpolation='lower')]
  outlier_df = outlier_df.nlargest(outlier_num, "percentage")
  if (write_to_csv):
    outlier_df.to_csv(lang + '_outliers.csv', index=False)
  return outlier_df
