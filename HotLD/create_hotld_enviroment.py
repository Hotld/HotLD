import os
import subprocess
import sys

LD_LIBRARY_PATH = os.environ.get("HOTLD_LIBRARY_PATH", "")
LD_LIBRARY_PATH = LD_LIBRARY_PATH.split(os.pathsep)
print(f"HOTLD_LIBRARY_PATH: {LD_LIBRARY_PATH}")


def get_library_paths(binary_path):
    """
    Get the absolute paths of all shared libraries required by the binary.

    Args:
        binary_path (str): Path to the binary file.

    Returns:
        list: List of absolute paths of shared libraries.
    """
    if not os.path.isfile(binary_path):
        raise FileNotFoundError(f"Binary file not found: {binary_path}")

    try:
        result = subprocess.run(
            ['ldd', binary_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ldd command failed: {result.stderr.strip()}")

        library_paths = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if '=>' in line:
                parts = line.split('=>')
                if len(parts) > 1:
                    lib_path = parts[1].split()[0].strip()
                    if os.path.isabs(lib_path):
                        library_paths.append(lib_path)
            elif line:
                lib_name = line.split()[0].strip()
                if os.path.isabs(lib_name):
                    library_paths.append(lib_name)
        return library_paths
    except FileNotFoundError:
        raise RuntimeError(
            "ldd command not found. Ensure it is installed and available in your PATH.")
    except Exception as e:
        raise RuntimeError(f"An error occurred while parsing libraries: {e}")


def copy_library_with_sudo(library_path, target_dir):
    """
    Copy a shared library to the target directory using sudo if it does not already exist.

    Args:
        library_path (str): Absolute path of the shared library.
        target_dir (str): Target directory path.
    """

    if not os.path.isabs(library_path):
        raise ValueError("Library path must be an absolute path.")
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, os.path.basename(library_path))
    if not os.path.exists(target_path):
        try:
            subprocess.run(
                ['sudo', 'cp', library_path, target_path], check=True)
            print(f"Copied with sudo: {library_path} -> {target_path}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to copy {library_path} with sudo: {e}")
    else:
        print(f"Skipped: {library_path} (already exists in {target_dir})")


def mov_libraries_to_hotld(binary_path):
    target_dir = LD_LIBRARY_PATH[0]
    try:
        libraries = get_library_paths(binary_path)
        for lib in libraries:
            copy_library_with_sudo(lib, target_dir)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python 2_generate_app_cfg <binary_path> ")
        sys.exit(1)

    binary_path = sys.argv[1]
    mov_libraries_to_hotld(binary_path)
