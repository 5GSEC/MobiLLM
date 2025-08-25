import os
import subprocess

# Paths to the sample data files
UE_FILE = os.path.join(os.path.dirname(__file__), "5G-Sample-Data - UE.csv")
BS_FILE = os.path.join(os.path.dirname(__file__), "5G-Sample-Data - BS.csv")
MOBIEXPERT_EVENT_FILE = os.path.join(os.path.dirname(__file__), "5G-Sample-Data - Event - MobieXpert.csv")
MOBIWATCH_EVENT_FILE = os.path.join(os.path.dirname(__file__), "5G-Sample-Data - Event - MobiWatch.csv")

# SDL parameters
POD_NAME = "statefulset-ricplt-dbaas-server-0"
NAMESPACE = "ricplt"

def execute_command(command):
    """Executes a shell command and returns the output and exit code."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def insert_to_sdl(namespace, key, value):
    """Insert a key-value pair into SDL using kubectl exec and sdlcli."""
    # Escape value for shell (wrap in single quotes, escape any single quotes inside)
    safe_value = value.replace("'", "'\"'\"'")
    command = (
        f"kubectl exec -it {POD_NAME} -n {NAMESPACE} -- "
        f"sdlcli set {namespace} {key} '{safe_value}'"
    )
    output, code = execute_command(command)
    if code != 0:
        print(f"Failed to insert key {key} into namespace {namespace}: {output}")
    else:
        print(f"Inserted key {key} into namespace {namespace}")

def process_file(file_path, namespace):
    """Read a file and insert each line as a key-value pair into SDL."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            value = line.strip()
            value = "€€" + value
            if not value:
                continue
            key = str(idx)
            insert_to_sdl(namespace, key, value)

if __name__ == "__main__":
    # Insert UE data
    print("Inserting UE data...")
    process_file(UE_FILE, "ue_mobiflow")

    # Insert BS data
    print("Inserting BS data...")
    process_file(BS_FILE, "bs_mobiflow")

    # Insert MobieXpert event data
    print("Inserting MobieXpert event data...")
    process_file(MOBIEXPERT_EVENT_FILE, "mobiexpert-event")

    # Insert MobiWatch event data
    print("Inserting MobiWatch event data...")
    process_file(MOBIWATCH_EVENT_FILE, "mobiwatch-event")
