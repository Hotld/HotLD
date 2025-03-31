import json
import sys
import subprocess
import sys
import os
from generate_hot_library_3 import generate_hot_library
from Bolted2Hotld import bolted2Hotld


def check_tool_installed(tool):
    try:
        subprocess.run([tool, '--version'], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        print(
            f"Error: {tool} is not installed. Please install it before running the script.")
        sys.exit(1)


# Check if objdump and nm are installed
check_tool_installed('objdump')
check_tool_installed('nm')

LLVM_TOOLS_PATH = os.environ.get('LLVM_TOOLS_PATH')

# Construct the full path to llvm-bat-dump
llvm_bat_dump_path = os.path.join(LLVM_TOOLS_PATH, 'llvm-bat-dump')

# Check if llvm-bat-dump exists at the specified path
if not os.path.isfile(llvm_bat_dump_path):
    print(
        f"Error: llvm-bat-dump not found at {llvm_bat_dump_path}. Please check the LLVM_TOOLS_PATH.")
    sys.exit(1)


def match_hot_and_bolted_libraries(config_data):
    # Parse the JSON file and match hot_library with bolted_library,
    # storing the result in a dictionary

    exe_file = config_data["exe_file"]
    hot_libraries = config_data.get("hot_library", [])
    bolted_libraries = config_data.get("bolted_library", [])

    # Check if the lengths of the two lists are consistent
    if len(hot_libraries) != len(bolted_libraries):
        print("Error: The number of hot libraries and bolted libraries do not match.")
        return

    # Store the corresponding results in a dictionary
    library_mapping = {}
    for hot_lib, bolted_lib in zip(hot_libraries, bolted_libraries):
        library_mapping[hot_lib] = bolted_lib

    print("Matching hot_library with bolted_library:")
    for hot_lib, bolted_lib in library_mapping.items():
        print(f"Hot library: {hot_lib} -> Bolted library: {bolted_lib}")

    return exe_file, library_mapping


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python script.py <config_file> <script_file> <output_dir>")
        sys.exit(1)

    config_file = sys.argv[1]
    script_file = sys.argv[2]
    output_dir = sys.argv[3]

    try:
        # load JSON file
        with open(config_file, 'r') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {config_file} does not exist.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {config_file}.")
        sys.exit(1)

    exe_file, library_mapping = match_hot_and_bolted_libraries(config_data)

    rela_infos = {}
    for library, bolted_library in library_mapping.items():
        rela_info_file = f"{os.path.basename(library)}_rela.json"
        rela_info_file = os.path.join(output_dir, rela_info_file)
        internal_relocations_file = f"{os.path.basename(library)}_internal_relocations.json"
        internal_relocations_file = os.path.join(
            output_dir, internal_relocations_file)

        bolted2Hotld(library, bolted_library, rela_info_file,
                     internal_relocations_file)
        rela_infos[library] = {
            "bolted_library": bolted_library,
            "rela_info": rela_info_file,
            "internal_relocations": internal_relocations_file
        }
    config_data["library_infos"] = rela_infos

    generate_hot_library(config_data, output_dir)

    with open((config_file), "w") as file:
        json.dump(config_data, file, indent=4)
