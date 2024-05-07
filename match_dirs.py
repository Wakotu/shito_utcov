import os


def find_matching_directories(root_dir, target_dir):
    matching_dirs = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        if target_dir in dirpath:
            matching_dirs.append(dirpath)
    return matching_dirs


root_directory = "."
target_directory = "target/surefire-reports"

matching_directories = find_matching_directories(
    root_directory,
    target_directory,
)
print("Matching directories:")
for directory in matching_directories:
    print(directory)
