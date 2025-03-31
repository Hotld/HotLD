import logging
from common import *
from template import TemplateHotLibrary
import json


def link_got_relocation(HotLibrary: TemplateHotLibrary, total_got_relocations):
    results = {}
    for hot_library in total_got_relocations.keys():
        hot_library_bbs_info = None
        for item in HotLibrary.librarymetas:
            if hot_library == item.name:
                hot_library_bbs_info = item
                break

        if hot_library_bbs_info == None:
            return None
        ori_hotbbs_range = hot_library_bbs_info.ori_hotbbs_range
        optimized_hotbbs_range = hot_library_bbs_info.hotcode_range
        # cold_bbs_range = get_section_addresses(bolted_library, COLD_BBS_NAME)
        for parent_lib in total_got_relocations[hot_library].keys():
            cur_got_relocations = total_got_relocations[hot_library][parent_lib]
            modifed_got_relocations = []
            for r_offset, rela_info in cur_got_relocations.items():
                r_hot_target = rela_info["r_hot_target"]
                if ori_hotbbs_range[0] <= r_hot_target < ori_hotbbs_range[1]:
                    r_hot_target = r_hot_target - \
                        ori_hotbbs_range[0]+optimized_hotbbs_range[0]
                    rela_info["r_hot_target"] = r_hot_target
                    modifed_got_relocations.append(rela_info)
                else:
                    logging.error(f"link got relocation {rela_info} failed")

            if parent_lib not in results.keys():
                results[parent_lib] = modifed_got_relocations
            else:
                results[parent_lib].extend(modifed_got_relocations)

    return results


def link_text_relocation(HotLibrary: TemplateHotLibrary, config_data):
    """
    Link the text relocations of the hotLib by adjusting the offsets of the
    relocation entries in each instruction based on their new position in the HotLibrary.

    :param HotLibrary: The HotLib object where the relocated code will be linked.
    :param config_data: Configuration data containing library and relocation information.
    :return: A dictionary mapping each library to its internal relocations after being adjusted.
    """

    # Extract hot libraries and corresponding relocation information from config data
    hot_librarys = config_data["hot_library"]
    library_rela_infos = config_data["library_infos"]

    # Dictionary to store the final internal relocations for all libraries
    total_internal_relocation = {}

    # Iterate through each hot library in the configuration data
    for library in hot_librarys:
        # Read the internal relocation information for the current library
        internal_relocations_file = library_rela_infos[library]["internal_relocations"]
        with open(internal_relocations_file, 'r') as f:
            internal_relocations = json.load(f)

        # Find the corresponding HotLibrary meta information
        hot_library_bbs_info = None
        for item in HotLibrary.librarymetas:
            if library == item.name:
                hot_library_bbs_info = item
                break

        # If no matching bbs info found, return None
        if hot_library_bbs_info is None:
            return None

        ori_hotbbs_range = hot_library_bbs_info.ori_hotbbs_range
        optimized_hotbbs_range = hot_library_bbs_info.hotcode_range
        ori_coldbbs_range = hot_library_bbs_info.ori_coldbbs_range
        optimized_coldbbs_range = hot_library_bbs_info.coldcode_range

        # List to store the adjusted relocations for the current library
        cur_library_relocations = []

        # Iterate through all functions and their relocation information
        for func, relocations in internal_relocations.items():
            if internal_relocations[func] == {}:
                continue

            for key in relocations.keys():
                r_offset = int(key)
                r_target = relocations[key]["target_offset"]

                # Adjust r_offset based on HotLib
                if ori_hotbbs_range[0] < r_offset < ori_hotbbs_range[1]:
                    r_offset = r_offset - \
                        ori_hotbbs_range[0] + optimized_hotbbs_range[0]
                elif ori_coldbbs_range[0] < r_offset < ori_coldbbs_range[1]:
                    r_offset = r_offset - \
                        ori_coldbbs_range[0] + optimized_coldbbs_range[0]
                else:
                    logging.error(
                        f"The internal relocation {relocations[key]} r_offset {hex(r_offset)}({r_offset}) parse error")

                # Modify the target offset (r_target)
                if relocations[key]["r_type"] == 777:
                    if ori_coldbbs_range[0] <= r_target < ori_coldbbs_range[1]:
                        r_target = r_target - \
                            ori_coldbbs_range[0] + optimized_coldbbs_range[0]
                    else:
                        logging.error(
                            f"The internal relocation {relocations[key]} r_target {hex(r_target)}({r_target}) parse error")
                elif relocations[key]["r_type"] == 778:
                    if ori_hotbbs_range[0] <= r_target < ori_hotbbs_range[1]:
                        r_target = r_target - \
                            ori_hotbbs_range[0] + optimized_hotbbs_range[0]
                    else:
                        logging.error(
                            f"The internal relocation {relocations[key]} r_target {hex(r_target)}({r_target}) parse error")

                # Append the modified relocation data to the list for the current library
                cur_library_relocations.append({
                    "r_offset": r_offset,
                    "r_hot_target": r_target,
                    "r_type": relocations[key]["r_type"],
                    "dist_next_instr": relocations[key]["dist_next_instr"]
                })

        # Store the adjusted relocations for the current HotLib
        total_internal_relocation[library] = cur_library_relocations

    return total_internal_relocation
