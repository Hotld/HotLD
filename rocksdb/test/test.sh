#!/bin/bash
exe_file="$1"
workdir="$2"

current_dir=$(pwd)
num_iterations=1
log_file="log0331_ORI"

total_benchmarks=("fillseq","fillrandom","readrandom,readrandomwriterandom" "readseq" "overwrite,readrandom" "readrandom" "readrandomwriterandom" "overwrite" "updaterandom")

benchmarks=("readrandom")


testdb="$HOME/Desktop/testdb"
for benchmark in "${benchmarks[@]}"; do
    case "$benchmark" in
        fillseq|fillrandom)
            argvs=" --benchmarks=$benchmark --num=10000000 --duration=40 -report_file=log0217 -report_interval_seconds=1 "

            for ((i=1; i<=num_iterations; i++)); do
                # test ori
                echo "[Begin] Test the original settings $num_iterations times." | tee -a $log_file
                ./pre_benchmark_ori.sh $exe_file "$argvs" | tee -a $log_file
                echo "[End] original settings test finish." | tee -a $log_file
                rm -rf $testdb
                
            done
            ;;
        readrandom|updaterandom|overwrite|overwrite,readrandom)
            argvs=" --benchmarks=$benchmark --duration=30 --use_existing_db=true -use_existing_keys=true  --db=$testdb -report_file=log0217 -report_interval_seconds=1 "

            for ((i=1; i<=num_iterations; i++)); do
                # test ori
                $exe_file --benchmarks=fillrandom --num=2000000 --db=$testdb
                echo "[Begin] Test the original settings $num_iterations times." | tee -a $log_file
                ./pre_benchmark_ori.sh $exe_file $argvs | tee -a $log_file
                echo "[End] original settings test finish." | tee -a $log_file
                rm -rf $testdb
                
            done
            ;;
        readseq)
            argvs=" --benchmarks=$benchmark --duration=60 --use_existing_db=true -use_existing_keys=true  --db=$testdb -report_file=log0217 -report_interval_seconds=1 "

            for ((i=1; i<=num_iterations; i++)); do
                # test ori
                $exe_file --benchmarks=fillrandom --num=10000000 --db=$testdb
                echo "[Begin] Test the original settings $num_iterations times." | tee -a $log_file
                ./pre_benchmark_ori.sh $exe_file $argvs | tee -a $log_file
                echo "[End] original settings test finish." | tee -a $log_file
                rm -rf $testdb
                
            done
            ;;
        *)
            ;;
    esac
done
