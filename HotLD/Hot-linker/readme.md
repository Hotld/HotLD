# Compile Hot-Linker
gcc -shared -fPIC hotld.c -o HotLinker.so


# Use Hot-Linker
LD_PRELOAD=/path/to/HotLinker.so exefile [...]