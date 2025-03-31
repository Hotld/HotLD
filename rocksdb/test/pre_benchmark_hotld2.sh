#!/bin/bash
exe_file="$1"
shift
hot_linker="$1"
shift
hot_libs="$1"
shift
argvs="$@"

export LD_BIND_NOW=1
export HOTLD_HOTLIBS=$hot_libs

LD_PRELOAD=$hot_linker $exe_file $argvs