import os
import json
import subprocess
import sys


def load_config(config_file):
    """Load JSON configuration file."""
    if not os.path.isfile(config_file):
        raise FileNotFoundError(f"Config file not found: {config_file}")
    with open(config_file, 'r') as f:
        return json.load(f)


def run_command(command, error_message):
    """Run a shell command and handle errors."""
    result = subprocess.run(command, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{error_message}: {result.stderr.strip()}")
    return result.stdout.strip()


def process_libraries(hot_libraries, perf_data_path, output_dir):
    """Optimize shared libraries using perf2bolt and llvm-bolt."""
    optimized_libraries = []
    for lib in hot_libraries:
        print(f"Processing library: {lib}")
        perf_fdata = os.path.join(output_dir, "perf.fdata")
        output_lib = os.path.join(output_dir, os.path.basename(lib))
        # Run perf2bolt
        run_command([
            "perf2bolt", "-p", perf_data_path, "-o", perf_fdata, lib, "--skip-funcs=RC4_options"
        ], f"perf2bolt failed for {lib}")

        # Run llvm-bolt
        run_command([
            "llvm-bolt", lib, "-o", output_lib, "-data", perf_fdata,
            "-reorder-blocks=ext-tsp", "-reorder-functions=hfsort", "-split-functions",
            "-split-all-cold", "-split-eh", "-dyno-stats", "--enable-bat", "--jump-tables=none", "--print-cfg"
        ], f"llvm-bolt failed for {lib}")

        print(
            f"Optimization completed for {lib}. Optimized file saved at {output_lib}.")
        optimized_libraries.append(output_lib)
    return optimized_libraries


def main(config_file, perf_data_path, output_dir):
    """Main function to process libraries based on perf data."""
    config = load_config(config_file)
    exe_file = config.get("exe_file")
    hot_libraries = config.get("hot_library", [])

    print(f"Executable file: {exe_file}")
    print("Hot libraries:")
    for lib in hot_libraries:
        print(lib)

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    optimized_libraries = process_libraries(
        hot_libraries, perf_data_path, output_dir)

    config["bolted_library"] = optimized_libraries

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)

    print("JSON file updated successfully.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python script.py <config_file> <perf_data_path> <output_dir>")
        sys.exit(1)

    config_file = sys.argv[1]
    perf_data_path = sys.argv[2]
    output_dir = sys.argv[3]

    main(config_file, perf_data_path, output_dir)
