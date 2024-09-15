"""Script to write IR dataset files to a specified storage location.

Two functions are contained in the script. One function retrieves a
storage location argument for the script. The other function accesses
the ComPile dataset using the Hugging Face API and writes the bitcode
files in the dataset to tar files corresponding to their IR language.

the index counts for each language are written to a file "indices.csv".
Then, each bitcode file is written using available threads into
respective tar files named [lang]_bc_files.tar. Each file added to a tar
file is named bc_files/file[index].bc, where index is a number that is
between the range of start_index and end_index (not including end) in
"indices.csv" and is incremented by one (smallest index is 1).

Example usage: python write_data_files.py /tmp
"""

import argparse
from datasets import load_dataset, parallel
from os import makedirs, listdir
import threading
import csv
import tarfile
from io import BytesIO
from time import time


def get_args():
  """Function to return the provided storage argument for the script.

  Returns: argparse.Namespace
  """

  parser = argparse.ArgumentParser(
      description="Configure path to store bitcode files, and configure batch size."
  )
  parser.add_argument('storage', type=str, help='Path to the storage location.')
  return parser.parse_args()


def write_dataset_files_and_index_info(storage: str) -> None:
  """Function to write each IR bitcode file to a tar archive.

  The function first loads the ComPile dataset into a HF datasets
  Dataset object. It does this using an experimental parallel backend to
  slightly speed up load times. Then, a list of dictionaries is made,
  where each dict contains the starting and ending index for each IR
  file type based on language. For example, if the entire dataset
  consisted of C and C++ IR modules, then the dictionary for C would
  note language='c', starting_index=0, ending_index=(C++ starting
  index). The +1 for the ending_index allows for direct use in range(a,
  b) syntax, but is NOT suitable for right inclusive syntax. The entries
  of each dictionary are then written to a CSV file name 'indices.csv'
  for further use by other scripts. The contents of each dictionary are
  used to provide information to the n number of threads, where n is the
  number of languages in the dataset. Each thread when started calls the
  create_tar() sub-function. The sub-function uses a generator
  expression to access the bitcode files from a subset (taken by
  language) of the original Dataset object. This allows for low memory
  usage while performing in-memory writing of each bitcode file to a tar
  archive which is named according to the given language (i.e.,
  c_bc_files.tar).

  Args:
    storage: Storage location for the tar archives
  """

  def create_tar(dataset_subset, start_index: int, dir_name: str,
                 language: str):
    with tarfile.open(dir_name + '/' + language + '_bc_files.tar', 'a:') as tar:
      for x in enumerate((dataset_subset[i]["content"]
                          for i in range(0, dataset_subset.num_rows))):
        tarinfo = tarfile.TarInfo(name=f'bc_files/file{x[0]+1+start_index}.bc')
        file_obj = BytesIO(x[1])
        tarinfo.size = file_obj.getbuffer().nbytes
        tarinfo.mtime = time()
        tar.addfile(tarinfo, fileobj=file_obj)

  with parallel.parallel_backend('spark'):
    dataset = load_dataset('llvm-ml/ComPile', split='train', num_proc=2)

  lang_list: [str] = dataset["language"]
  langs = dataset.unique("language")
  file_indices: [dict] = []

  for i in range(0, len(langs)):
    start_index = lang_list.index(langs[i])
    if (i + 1 != len(langs)):
      end_index = lang_list.index(langs[i + 1])
    else:
      end_index = len(lang_list)
    file_indices.append({
        "language": langs[i],
        "start_index": start_index,
        "end_index": end_index
    })
    with open('indices.csv', mode='w', newline='') as file:
      writer = csv.DictWriter(
          file,
          fieldnames=["language", "start_index", "end_index"],
          dialect='unix',
          quoting=csv.QUOTE_NONE)
      writer.writeheader()
      writer.writerows(file_indices)

  threads = []
  for i in range(0, len(file_indices)):
    start_index = file_indices[i]["start_index"]
    end_index = file_indices[i]["end_index"]
    dir_name = f'{storage}/{file_indices[i]["language"]}'
    makedirs(dir_name, exist_ok=True)
    thread = threading.Thread(
        target=create_tar,
        args=(dataset.select(range(start_index, end_index)), start_index,
              dir_name, file_indices[i]["language"]))
    threads.append(thread)
  for thread in threads:
    thread.start()
  for thread in threads:
    thread.join()


if __name__ == '__main__':
  args = get_args()
  write_dataset_files_and_index_info(storage=args.storage)
