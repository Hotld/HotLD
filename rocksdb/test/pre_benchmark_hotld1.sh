#!/bin/bash
exe_file="$1"
shift
hot_linker="$1"
shift
hot_lib="$1"
shift
argvs="$@"

export LD_BIND_NOW=1
export HOTLD_HOTLIB=$hot_lib

LD_PRELOAD=$hot_linker $exe_file $argvs
