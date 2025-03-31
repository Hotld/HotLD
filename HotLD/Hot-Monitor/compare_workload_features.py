import subprocess
import numpy as np


def calculate_cosine_similarity(vector1, vector2):
    if (len(vector1) == 0) | (len(vector2) == 0):
        return 0
    return np.dot(vector1, vector2) / (np.linalg.norm(vector1) * np.linalg.norm(vector2))


def transform_to_binary_vector(original_vector):
    no_zero_vector = [v for v in original_vector if v != 0]
    threshold = np.percentile(no_zero_vector, 20)
    # print(f"{len(no_zero_vector)}, {threshold}")

    binary_arr = (original_vector >= threshold).astype(int)
    return binary_arr


def transform_to_zero_vector(original_vector):
    no_zero_vector = [v for v in original_vector if v != 0]
    threshold = np.percentile(no_zero_vector, 50)

    result = [x if x >= threshold else 0 for x in original_vector]
    return result


def compute_binary_cosine_similarity(vector1, vector2):
    if (len(vector1) == 0) | (len(vector2) == 0):
        return 0
    binary_vector1 = transform_to_binary_vector(vector1)
    binary_vector2 = transform_to_binary_vector(vector2)
    cosine_similarity_binary = calculate_cosine_similarity(
        binary_vector1, binary_vector2)
    return round(cosine_similarity_binary, 4)


def extract_functions(so_file):
    try:
        result = subprocess.run(
            ["nm", so_file], capture_output=True, text=True, check=True)
        functions = [line.split()[-1] for line in result.stdout.splitlines()]
        return functions
    except subprocess.CalledProcessError as e:
        print(f"Error processing {so_file}: {e}")
        return []


def get_target_library_symbols(libraries):
    all_functions = {}
    for lib in libraries:
        functions = extract_functions(lib)
        for func in functions:
            all_functions[func] = []
    return all_functions.keys()


def compute_combined_similarities(value1, value3):
    alpha = 0.5
    beta = 0.5
    result = alpha*value1+beta*value3
    return round(result, 4)


def compute_stage2_similarity(workload_pairs, binary_cosin):
    funcCycle_cosin = [0]*len(workload_pairs.keys())
    combined_cosin = [0]*len(workload_pairs.keys())

    for key, values in workload_pairs.items():
        data1 = values["cur_workload"]
        data2 = values["static_workload"]
        vector1 = np.array([sum(data1[key]) for key in data1.keys()])
        vector2 = np.array([sum(data2[key]) for key in data1.keys()])
        funcCycle_cosin[key] = round(calculate_cosine_similarity(
            vector1, vector2), 4)
        combined_cosin[key] = compute_combined_similarities(
            binary_cosin[key], funcCycle_cosin[key])
    return list(zip(binary_cosin, funcCycle_cosin, combined_cosin))
