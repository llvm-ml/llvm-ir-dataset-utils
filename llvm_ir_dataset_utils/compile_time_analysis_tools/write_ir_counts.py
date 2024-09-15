"""Script to print function analysis properties for IR bitcode files.

The script uses argparse to expect a bitcode file path as argument. The
main function invokes a print() to display the imported function's
output.

Example usage:
  python write_ir_counts.py /tmp/c/file1.bc 
  python write_ir_counts.py /dev/null
"""
from llvm_ir_dataset_utils.util.bitcode_module import get_function_properties_total
import argparse
from datasets import load_dataset, parallel


def main() -> None:
  """Function takes a bitcode filename from argparse and prints the function
  analysis properties counts for that file.

  If a valid bitcode file is provided to argparse, the counts will be
  printed using llvm_ir_dataset_utils.util.bitcode_module.get_function_p
  roperties_total. The bitcode file is loaded into memory as a bytes
  object to pass in as an argument. If "/dev/null" is provided to
  argparse, the Hugging Face IR dataset will be loaded and the loop will
  start from the first index of the dataset to obtain a bitcode file
  with valid function analysis properties field names. Each output is
  comma seperated values.
  """
  parser = argparse.ArgumentParser(
      description="Process a bitcode file and print field counts.")
  parser.add_argument(
      'filename', type=str, help="Path to the bitcode (.bc) file.")
  filename = parser.parse_args().filename
  if (filename == "/dev/null"):
    with parallel.parallel_backend('spark'):
      dataset = load_dataset('llvm-ml/ComPile', split='train', num_proc=2)
    for i in range(0, dataset.num_rows):
      bc_file = dataset[i]["content"]
      output = get_function_properties_total(bc_file, names=True)
      if (output != None):
        print(', '.join(output))
        break
  else:
    print(', '.join(
        str(x)
        for x in get_function_properties_total(open(filename, "rb").read())))


if __name__ == '__main__':
  main()
