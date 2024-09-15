# Compile Time Analysis Tools

- SLURM_files/batch_main_body.sh
- SLURM_files/create_batch_files.sh
- SLURM_files/job_template.sh
- Makefile
- combine_outputs.sh
- write_ir_counts.py

**create_batch_files.sh** must be provided a storage argument, temporary \
directory argument, and a path to the relevant makefile (where \
Makefile is). Other configurable args are the number of threads used \
by the make command in the batch scripts, and the maximum number of \
SLURM jobs which a user can have in the SLURM queue. 

Examples:
  `./create_batch_files.sh /lustre /tmp 
  path_to_ir_dataset_repo/llvm_ir_dataset_utils/compile_time_analysis_tools`

  `./create_batch_files.sh /lustre /tmp
    path_to_ir_dataset_repo/llvm_ir_dataset_utils/compile_time_analysis_tools
    32 400`

When executed, settings will be configured for batch job scripts which are \
created in the format [_language_extension_]batch.sh. The content of those \
scripts is a combination of **job_template.sh** (from SLURM config) and \
**batch_main_body.sh** (for the main execution).

**write_ir_counts.py** is automatically used by **Makefile** to generate \
IR features count data for each IR module being processed.

**combine_outputs.sh** takes two args: <language_extension> and \
<storage_location>. Example: `./combine_outputs.sh c /lustre`. The \
script combines all the temporary result folders made in \
<storage_location>/<language_extension>/. It removes the folders and \
creates temporary files from which the final csv files are constructed \
for the given language. Current data collected includes text segment \
size, user CPU instruction counts during compile time, IR feature \
counts sourced from the LLVM pass `print<func-properties>`, and maximum \
relative time pass names and percentage counts.
