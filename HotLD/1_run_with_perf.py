import os
import sys
from create_hotld_enviroment import *


def run_command(command, exit_on_fail=True):
    print(f"Running command: {' '.join(command)}")
    result = subprocess.run(command, shell=False)
    if result.returncode != 0 and exit_on_fail:
        print(
            f"Error: Command {' '.join(command)} failed with code {result.returncode}")
        sys.exit(result.returncode)


def main():
    if len(sys.argv) < 3:
        print(
            f"Usage: {sys.argv[0]} <working_directory> <command> [arguments...]")
        sys.exit(1)

    work_dir = sys.argv[1]
    command = sys.argv[2]
    command_args = sys.argv[3:]

    if not os.path.exists(work_dir):
        print(f"Creating working directory: {work_dir}")
        os.makedirs(work_dir)

    os.chdir(work_dir)

    mov_libraries_to_hotld(command)

    os.environ["LD_PRINT_LIBS"] = "1"

    # perf argvs
    perf_output = f"{work_dir}/perf.data"
    perf_event = "cycles:u"
    perf_options = "-j any,u"

    # excute perf record
    perf_command = ["perf", "record", "-e", perf_event, *
                    perf_options.split(), "-F", "5499", "-o", perf_output, command, *command_args]
    run_command(perf_command)

    print(
        f"Perf record completed successfully. Data saved to {work_dir}/{perf_output}.")


if __name__ == "__main__":
    main()
