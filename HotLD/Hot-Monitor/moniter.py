import os
import time
import subprocess
import logging
import sys
import socket
from select_hotlibrary import *

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def send_value(socket_path, value):

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)

        sock.send(struct.pack('i', value))
        sock.close()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) != 6:
        logging.error("Usage: {} <n_seconds> <m_seconds> <threshold> <output_dir> <pid> ".format(
            sys.argv[0]))
        sys.exit(1)

    INTERVAL = int(sys.argv[1])
    PERF_DURATION = float(sys.argv[2])
    THRESHOLD = float(sys.argv[3])
    OUTPUT_DIR = sys.argv[4]
    PID = sys.argv[5]

    MAPPED_INFOS = os.path.expanduser(f"~/hotld/tmp/mapinfo_{PID}.txt")
    LOGFILE = f"{PID}.log"
    SOCKET_PATH = f"/tmp/hotld_{PID}_socket"
    COUNT = 0

    mapinfo_data = parse_mapinfo_file(MAPPED_INFOS)
    hotlibrary_mapinfos = get_hotlibrary_infos(mapinfo_data)

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    last_index = -1
    while True:
        # Check if the process is still running
        try:
            subprocess.check_call(
                ['ps', '-p', PID], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            logging.info(f"Process {PID} has ended. Exiting.")
            break

        OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"perf_{PID}_{COUNT}.data")
        perf_record_commond = f"perf record -e cycles:u -j any,u -p {PID} -o {OUTPUT_FILE} -- sleep {PERF_DURATION} "
        # logging.info(f"{perf_record_commond}")
        execute_command(perf_record_commond)
        COUNT += 1

        start_time = time.time()

        max_index, total_result = select_hotlibrary(OUTPUT_FILE,
                                                    mapinfo_data, hotlibrary_mapinfos, THRESHOLD)

        with open(LOGFILE, "a") as file:
            file.write(f"{os.path.basename(OUTPUT_FILE)} result:\n")
            table_str = print_results_as_table(
                mapinfo_data, total_result)
            file.write(table_str)
            file.write(
                f"\nmapped hotlibrary is {mapinfo_data[max_index]['ht_path']}\n")

            if (max_index != -1) & (max_index != last_index):
                file.write(
                    f"last_hotlibrary_index:{last_index}, cur_hotlibrary_index:{max_index}\n")
                send_value(SOCKET_PATH, max_index)
                last_index = max_index

        end_time = time.time()
        elapsed_time = end_time - start_time
        logging.info(f"Script execution time: {elapsed_time} seconds")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
