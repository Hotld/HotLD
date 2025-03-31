#!/bin/bash

# Set HOTLD_LIBRARY_PATH and update LD_LIBRARY_PATH
export HOTLD_LIBRARY_PATH="/usr/local/hotld"
export LD_LIBRARY_PATH="/usr/local/hotld:$LD_LIBRARY_PATH"

# Append to .bashrc
echo "export HOTLD_LIBRARY_PATH=/usr/local/hotld" >> "$HOME/.bashrc"
echo "export LD_LIBRARY_PATH=/usr/local/hotld:$LD_LIBRARY_PATH" >> "$HOME/.bashrc"

# Apply changes
source "$HOME/.bashrc"
