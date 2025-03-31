#!/bin/bash
exe_file="$1"
shift
argvs="$@"

export LD_BIND_NOW=1

$exe_file $argvs