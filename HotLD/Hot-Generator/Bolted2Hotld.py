import os
import sys
import subprocess


def bolted2Hotld(ORI_ELF_PATH, BOLTED_ELF_PATH, RELA_INFO_FILE, INTERNAL_RELOCATIONS_FILE):

    LLVM_TOOLS_PATH = os.environ.get('LLVM_TOOLS_PATH')

    # Construct the full path to llvm-bat-dump
    llvm_bat_dump_path = os.path.join(LLVM_TOOLS_PATH, 'llvm-bat-dump')

    # Check if llvm-bat-dump exists at the specified path
    if not os.path.isfile(llvm_bat_dump_path):
        print(
            f"Error: llvm-bat-dump not found at {llvm_bat_dump_path}. Please check the LLVM_TOOLS_PATH.")
        sys.exit(1)

    # Create a temporary directory to store the output
    TEMP_OUTPUT_DIR = './intermediate_file'

    if not os.path.exists(TEMP_OUTPUT_DIR):
        os.makedirs(TEMP_OUTPUT_DIR)
        print(f"Created directory: {TEMP_OUTPUT_DIR}")
    else:
        print(f"Directory already exists: {TEMP_OUTPUT_DIR}")

    # Generate the output file name based on the bolted ELF file
    llvm_bat_output = f"{TEMP_OUTPUT_DIR}/{os.path.basename(BOLTED_ELF_PATH)}_llvm_bat_output"

    # Run llvm-bat-dump and redirect the output to the temporary file
    print(f"Running llvm-bat-dump on bolted ELF file: {BOLTED_ELF_PATH}")
    try:
        subprocess.run([llvm_bat_dump_path, '--dump-all', BOLTED_ELF_PATH],
                       check=True, stdout=open(llvm_bat_output, 'w'))
        print(
            f"llvm-bat-dump completed successfully. Output stored in: {llvm_bat_output}")
    except subprocess.CalledProcessError:
        print("Error: llvm-bat-dump failed.")
        sys.exit(1)

    # Define output file name
    LIBRARY_NAME = os.path.basename(ORI_ELF_PATH)
    BOLTED_FUNCTIONS_INFO = os.path.join(
        TEMP_OUTPUT_DIR, f"{LIBRARY_NAME}_bolted_functions_info.json")

    # Get current script directory
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

    # Run Python script 1_extract_hot_functions.py
    print(
        f"[stage1] python3 {os.path.join(SCRIPT_DIR, '1_extract_hot_functions.py')} {BOLTED_ELF_PATH} {llvm_bat_output} {BOLTED_FUNCTIONS_INFO}")
    try:
        subprocess.run(['python3', os.path.join(SCRIPT_DIR, '1_extract_hot_functions.py'),
                        BOLTED_ELF_PATH, llvm_bat_output, BOLTED_FUNCTIONS_INFO], check=True)
        print("[stage1] 1_extract_hot_functions script completed successfully.")
    except subprocess.CalledProcessError:
        print("[stage1] Error: 1_extract_hot_functions script failed.")
        sys.exit(1)

    # Run Python script 2_extract_instructions_target.py
    print(f"[stage2] python3 {os.path.join(SCRIPT_DIR, '2_extract_instructions_tartget.py')} {ORI_ELF_PATH} {BOLTED_ELF_PATH} {BOLTED_FUNCTIONS_INFO} {RELA_INFO_FILE} {INTERNAL_RELOCATIONS_FILE}")
    try:
        subprocess.run(['python3', os.path.join(SCRIPT_DIR, '2_extract_instructions_tartget.py'), ORI_ELF_PATH,
                        BOLTED_ELF_PATH, BOLTED_FUNCTIONS_INFO, RELA_INFO_FILE, INTERNAL_RELOCATIONS_FILE], check=True)
        print("[stage2] 2_extract_instructions_tartget script completed successfully.")
    except subprocess.CalledProcessError:
        print("[stage2] Error: 2_extract_instructions_tartget script failed.")
        sys.exit(1)
