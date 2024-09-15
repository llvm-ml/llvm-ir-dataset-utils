#!/bin/bash
set -o errexit

#Usage:
#./combine_outputs.sh <language> <storage>

if [ -z "$1" ]; then
  echo "Missing language argument."
  exit 1
else
  LANGUAGE="$1"
fi

if [ -z "$2" ]; then
  echo "Missing storage argument."
  exit 1
else
  STORAGE="$2"
fi


cd ${STORAGE}

mkdir -p ${LANGUAGE}/results
TARGET_PREFIX="${LANGUAGE}/results/${LANGUAGE}"

boolean=1
DATA_NAMES=("text_segment" "instruction" "ir_features" "max_pass")

for element in "${DATA_NAMES[@]}"; do
  if [[ ${element} == ${DATA_NAMES[2]} ]]; then
    OUTPUT=$(python3 -m llvm_ir_dataset_utils.compile_time_analysis_tools.write_ir_counts "/dev/null")
    echo "file, $OUTPUT" \
    > ${TARGET_PREFIX}_${element}.csv
  elif [[ ${element} == ${DATA_NAMES[3]} ]]; then
    echo "file, percentage, pass_name" \
    > ${TARGET_PREFIX}_${element}.csv
  else
    echo "file, ${element}" \
    > ${TARGET_PREFIX}_${element}.csv
  fi
  ls ${LANGUAGE}/ps_[0-9]*/${element}.csv | xargs cat \
  >> ${TARGET_PREFIX}_${element}.csv

  sort -nk1.5 ${TARGET_PREFIX}_${element}.csv \
  -o ${TARGET_PREFIX}_${element}.csv
  if [ $boolean -eq 1 ]; then
    awk -F',' '{print $1}' ${TARGET_PREFIX}_${DATA_NAMES[0]}.csv > ${TARGET_PREFIX}_combined.csv
    boolean=0
  fi
  awk -F',' -v OFS=',' 'NR==FNR {for (i=2; i<=NF; i++) cols[FNR]=(cols[FNR]?cols[FNR] OFS:"") $i; next} {print $0, cols[FNR]}' \
    ${TARGET_PREFIX}_${element}.csv \
    ${TARGET_PREFIX}_combined.csv \
    > ${TARGET_PREFIX}_temp.csv
  mv ${TARGET_PREFIX}_temp.csv ${TARGET_PREFIX}_combined.csv
  rm ${TARGET_PREFIX}_${element}.csv
done

sed -n -i '/, ,/!p' ${TARGET_PREFIX}_combined.csv

rm -r ${LANGUAGE}/ps_*
