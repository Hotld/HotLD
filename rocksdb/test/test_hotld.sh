#!/bin/bash
exe_file="$1"
hot_linker="$2"
hot_libs="$3"
pre_test_script="$4"

current_dir=$(pwd)
num_iterations=1
log_file="log0325_hotld"

total_benchmarks=("fillseq,fillrandom"  "readseq" "overwrite,updaterandom")

benchmarks=("readrandom")

rm -rf $log_file

testdb="$HOME/Desktop/testdb"

for benchmark in "${benchmarks[@]}"; do
    case "$benchmark" in
        fillseq|fillrandom)
            argvs=" --benchmarks=$benchmark --num=10000000 --duration=40 -report_file=log0217 -report_interval_seconds=1 "

            echo "[Begin] Test the hotld settings $num_iterations times." | tee -a $log_file
            $pre_test_script $exe_file "$hot_linker" "$hot_libs" "$argvs" | tee -a $log_file
            echo "[End] hotld settings test finish." | tee -a $log_file
            rm -rf $testdb
                
            ;;
        readrandom|updaterandom|overwrite|overwrite,readrandom)
            argvs=" --benchmarks=$benchmark --duration=30 --use_existing_db=true -use_existing_keys=true  --db=$testdb -report_file=log0217 -report_interval_seconds=1 "

            echo "[Begin] Test the hotld settings $num_iterations times." | tee -a $log_file
            $exe_file --benchmarks=fillrandom --num=2000000 --db=$testdb
            $pre_test_script $exe_file "$hot_linker" "$hot_libs" "$argvs" | tee -a $log_file
            echo "[End] hotld settings test finish." | tee -a $log_file
            rm -rf $testdb

            ;;
        readseq)
            argvs=" --benchmarks=$benchmark --duration=40 --use_existing_db=true -use_existing_keys=true  --db=$testdb -report_file=log0217 -report_interval_seconds=1 "

            echo "[Begin] Test the hotld settings $num_iterations times." | tee -a $log_file
            $exe_file --benchmarks=fillrandom --num=10000000 --db=$testdb
            $pre_test_script $exe_file "$hot_linker" "$hot_libs" "$argvs" | tee -a $log_file
            echo "[End] hotld settings test finish." | tee -a $log_file
            rm -rf $testdb

            ;;

        *)
            ;;
    esac
done