#!/bin/bash
set -o errexit

#USAGE
#./create_batch_files.sh <STORAGE_PATH> <TEMP_DIR> <MAKEFILE_PATH> [THREADS] \
#  [SLURM_MAX]

if [ -z "$1" ]; then
  echo "Missing storage argument."
  exit 1
else
  STORAGE="$1"
fi
if [ -z "$2" ]; then
  echo "Missing temporary directory argument."
  exit 1
else
  TEMP_DIR="$2"
fi
if [ -z "$3" ]; then
  echo "Missing makefile location argument."
  exit 1
else
  MAKE_PATH="$3"
fi
if [ -z "$4" ]; then
  THREADS=8
else
  THREADS="$4"
fi
if [ -z "$5" ]; then
  SLURM_MAX=399
else
  SLURM_MAX="$5"
  SLURM_MAX=$((SLURM_MAX-1))
fi

lang=()
start_ids=()
sizes=()

while IFS=',' read -r language start_index end_index; do
  lang+=($language)
  start_ids+=($start_index)
  sizes+=($((${end_index}-${start_index})))
done < <(tail -n +2 "../dataset_download/indices.csv")

length=${#lang[@]}

for (( i=0; i<$length; i++ ))
do
  mkdir -p ${STORAGE}/${lang[$i]}/job_results
  js="${lang[$i]}_batch.sh"
  cp job_template.sh $js
  if [ ${sizes[$i]} -le $SLURM_MAX ]; then
    echo "#SBATCH --array=0-$((${sizes[$i]}-1))" >> $js
  else
    echo "#SBATCH --array=0-${SLURM_MAX}" >> $js
  fi 

  echo "#SBATCH --output=${STORAGE}/${lang[$i]}/job_results/slurm-%A_%a.out" >> $js
  echo "#SBATCH --error=${STORAGE}/${lang[$i]}/job_results/slurm-%A_%a.out" >> $js

  echo "START=${start_ids[$i]}" >> $js
  echo "TYPE=${lang[$i]}" >> $js
  echo "SIZE=${sizes[$i]}" >> $js
  echo "STORAGE=${STORAGE}" >> $js
  echo "TEMP_DIR=${TEMP_DIR}" >> $js
  echo "MAKE_PATH=${MAKE_PATH}" >> $js
  echo "THREADS=${THREADS}" >> $js
  echo "export PYTHONPATH=\"${PYTHONPATH}\"" >> $js
  cat batch_main_body.sh >> $js
  chmod 744 $js
done

