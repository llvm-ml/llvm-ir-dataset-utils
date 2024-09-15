#!/bin/bash -l
#
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=8
#SBATCH --job-name=compiler_batch
#SBATCH --partition=standard
#SBATCH --time=0-00:10:00
#SBATCH --export=NONE
