SHELL := /bin/bash

WILD := $(shell echo {$(begin)..$(end)})

ifneq ($(CC), clang)
  $(warning WARNING: SETTING CC TO clang OR clang++)
  override CC := clang
  ifeq ($(lang), cpp)
  override CC := clang++ 
  endif
endif

all: $(WILD) 

$(WILD):
	@perf stat --no-big-num -e instructions:u -o \
		$(lang)/perf_stat_files/file$@.txt \
		$(CC) -O3 -c $(lang)/bc_files/file$@.bc \
		-o $(lang)/object_files/file$@.o
	@instruct=$$(awk '/instructions/ {print $$1}' \
		$(lang)/perf_stat_files/file$@.txt); \
		echo "file$@, $$instruct" >> $(lang)/instruction_counts/instruction$@.csv
	@size=$$(llvm-size $(lang)/object_files/file$@.o | awk 'NR==2 {print $$1}'); \
		echo "file$@, $$size" >> $(lang)/text_segment_counts/text_segment$@.csv
	@ir_features=$$(python3 -m llvm_ir_dataset_utils.compile_time_analysis_tools.write_ir_counts \
		$(lang)/bc_files/file$@.bc); \
		echo "file$@, $$ir_features" >> $(lang)/ir_features_counts/ir_features$@.csv
	@max_pass=$$($(CC) -w -c -ftime-report $(lang)/bc_files/file$@.bc -o /dev/null 2>&1 | \
		awk '!/ignoring feature/' | awk 'NR==7 {print $$(NF-1) ", " $$NF}' | sed 's/%)//'); \
		echo "file$@, $$max_pass" >> $(lang)/max_pass_counts/max_pass$@.csv 

