import json
import sys
import os
from template import *
from common import *
from collect_got_relocations import *
from link_relocations import *


def extract_and_merge_sections(file_paths, section_name):
    """
    Extract and merge sections with the specified name from multiple ELF files.

    :param file_paths: List of ELF file paths to process
    :param section_name: Name of the section to extract and merge
    :return: A tuple containing:
             - merged_data: A bytearray containing all merged section data
             - file_section_info: List of dictionaries with section information for each file
    """
    # Bytearray to store the merged data of the sections
    merged_data = bytearray()
    # List to store information about each section from the ELF files
    file_section_info = []

    # Iterate over all ELF files provided in file_paths
    for file_path in file_paths:
        # Open the ELF file
        with open(file_path, 'rb') as f:
            elffile = ELFFile(f)

            # Search for the section with the specified name in the ELF file
            for section in elffile.iter_sections():
                if section.name == section_name:
                    section_data = section.data()  # Extract the data of the section

                    # Padding the section data to be a multiple of 64 bytes
                    padding_length = (64 - len(section_data) % 64) % 64
                    section_data = section_data + b'\x00' * padding_length

                    # Record information about the section from the current ELF file
                    section_info = {
                        'file': file_path,  # Path to the ELF file
                        # Original address of the section
                        'original_address': section['sh_addr'],
                        # Original size of the section
                        'original_size': section['sh_size'],
                        # Start address in the merged data
                        'start_address': len(merged_data),
                        # End address in the merged data
                        'end_address': len(merged_data) + len(section_data),
                        'size': len(section_data)  # Size of the section data
                    }
                    file_section_info.append(section_info)

                    # Append the section data to the merged data bytearray
                    merged_data.extend(section_data)

    # Return the merged data and the section information
    return merged_data, file_section_info


def merge_optimized_codes(HotLibrary: TemplateHotLibrary, config_data):
    ori_librarys = config_data["hot_library"]
    library_infos = config_data["library_infos"]
    bolted_librarys = []
    for item in ori_librarys:
        bolted_librarys.append(library_infos[item]["bolted_library"])

    total_hotbbs_data, total_hotbbs_info = extract_and_merge_sections(
        bolted_librarys, HOT_BBS_NAME)
    total_coldbbs_data, total_coldbbs_info = extract_and_merge_sections(
        bolted_librarys, COLD_BBS_NAME)
    for item in total_hotbbs_info:
        print(f"hot bbs: {item}")
    for item in total_coldbbs_info:
        print(f"cold bbs: {item}")

    for item in total_coldbbs_info:
        item["start_address"] += len(total_hotbbs_data)
        item["end_address"] += len(total_hotbbs_data)
    total_hotbbs_data.extend(total_coldbbs_data)
    for item in total_coldbbs_info:
        print(f"cold bbs: {item}")

    HotLibrary.optimized_codes = total_hotbbs_data
    for index, library in enumerate(ori_librarys):
        cur_metadata = LibraryMetaData()
        cur_metadata.name = library
        cur_metadata.hotcode_range = (
            total_hotbbs_info[index]["start_address"], total_hotbbs_info[index]["end_address"])
        cur_metadata.coldcode_range = (
            total_coldbbs_info[index]["start_address"], total_coldbbs_info[index]["end_address"])
        cur_metadata.ori_hotbbs_range = (
            total_hotbbs_info[index]["original_address"], total_hotbbs_info[index]["original_address"]+total_hotbbs_info[index]["size"])
        cur_metadata.ori_coldbbs_range = (
            total_coldbbs_info[index]["original_address"], total_coldbbs_info[index]["original_address"]+total_coldbbs_info[index]["size"])
        HotLibrary.librarymetas.append(cur_metadata)

    # print(HotLibrary.optimized_codes)
    print("\n")
    print_library_metadata(HotLibrary.librarymetas)


def extract_hotlibrary_symbols(config_data):
    library_infos = config_data["library_infos"]
    symbols_infos = {}
    for lib in library_infos.keys():
        symbols_infos[lib] = {}

        bolted_lib = library_infos[lib]["bolted_library"]
        hotbbs_range = get_section_addresses(bolted_lib, HOT_BBS_NAME)
        coldbbs_range = get_section_addresses(bolted_lib, COLD_BBS_NAME)
        print(f"{bolted_lib}\nhot bbs: {hotbbs_range}\ncold bbs: {coldbbs_range}")
        hotbbs_symbols = get_functions_in_range(
            bolted_lib, hotbbs_range[0], hotbbs_range[1])
        coldbbs_symbols = get_functions_in_range(
            bolted_lib, coldbbs_range[0], coldbbs_range[1])

        hotbbs_symbols.sort(key=lambda x: x[0])
        coldbbs_symbols.sort(key=lambda x: x[0])

        cur_lib_symbols = {}
        for item in hotbbs_symbols:
            key = str((item[0]-hotbbs_range[0], item[1]-hotbbs_range[0]))
            if key in cur_lib_symbols.keys():
                cur_lib_symbols[key].append(item[2])
            else:
                cur_lib_symbols[key] = [item[2]]

        symbols_infos[lib]["hot_bbs"] = cur_lib_symbols

        cur_lib_symbols = {}
        for item in coldbbs_symbols:
            key = str((item[0]-coldbbs_range[0], item[1]-coldbbs_range[0]))
            if key in cur_lib_symbols.keys():
                cur_lib_symbols[key].append(item[2])
            else:
                cur_lib_symbols[key] = [item[2]]
        symbols_infos[lib]["cold_bbs"] = cur_lib_symbols

    config_data["symbols_info"] = symbols_infos
    return config_data


def generate_hot_library(config_data, hot_library_dir):
    """
    Generate a hot library by performing several steps such as merging optimized code, 
    collecting GOT relocations, linking the relocations, and finally generating the hot library.

    :param config_data: Configuration data containing details of the program and optimization
    :param hot_library_dir: Directory to store the generated hot library file
    """

    # Initialize a HotLibrary object to store the merged and linked code
    HotLibrary = TemplateHotLibrary()

    # 1. Merge the optimized code sections into the HotLibrary
    merge_optimized_codes(HotLibrary, config_data)

    # 2. Collect all GOT (Global Offset Table) relocations that need to be modified
    total_parent_got_relocations = collect_got_relocations(config_data)

    # 3. Link the GOT relocations by adjusting their target addresses to point to the hot template
    linked_got_relocations = link_got_relocation(
        HotLibrary, total_parent_got_relocations)
    HotLibrary.linked_got_relocations = linked_got_relocations

    # Optionally, save the linked GOT relocations to a JSON file for inspection
    with open("linked_got_relocations.json", "w") as file:
        json.dump(linked_got_relocations, file, indent=4)

    # 4. Link text relocations within the bolted code (e.g., inside the hot code sections)
    linked_text_relocations = link_text_relocation(HotLibrary, config_data)
    HotLibrary.linked_text_relocations = linked_text_relocations

    # Optionally, save the linked text relocations to a JSON file for inspection
    with open("linked_text_relocations.json", "w") as file:
        json.dump(linked_text_relocations, file, indent=4)

    # 5. Generate the HotLibrary binary data from the linked and optimized code
    HotLibrary_bytedata = HotLibrary.generate_hotLibrary()

    # Define the file path for the HotLibrary binary, appending the executable file name and ".ht" extension
    Hotlibrary_file = os.path.basename(config_data["exe_file"]) + ".ht"
    Hotlibrary_file = os.path.join(hot_library_dir, Hotlibrary_file)

    # Write the generated binary data to the HotLibrary file
    with open(Hotlibrary_file, 'wb') as f:
        f.write(HotLibrary_bytedata)
        print(f"Binary data has been written to {Hotlibrary_file}")

    # Extract the symbols from the generated HotLibrary for further processing
    config_data = extract_hotlibrary_symbols(config_data)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script.py <config_file>  <hot_library_dir>")
        sys.exit(1)

    config_file = sys.argv[1]
    hot_library_dir = sys.argv[2]

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

    generate_hot_library(config_data, hot_library_dir)

    with open(config_file, "w") as file:
        json.dump(config_data, file, indent=4)
