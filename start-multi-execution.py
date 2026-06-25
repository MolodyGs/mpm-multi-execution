import shutil
import subprocess
import threading
import json
import time
import sys
from pathlib import Path
import os
import zipfile

# Json template for testing (slope-failure)
json_template = {
"stress_scheme_update":"USL",
	"shape_function":"GIMP",
	"time":1,
	"time_step":0.001,
	"gravity":[0.0,0.0,-9.81],
	"n_threads":10,
	"damping":
	{
		"type":"local",
		"value":0.0
	},
	"results":
	{
		"print":50,
		"material-point-results":
		{
			"fields":["all"]
		},
		
		"grid-nodal-results":
		{
			"fields":["none"]
		}
	},
	"mesh":
	{	
		"cells_dimension":[1,1,1],
		"cells_number":[110,1,36],
		"origin":[0,0,0],
		"boundary_conditions":
		{
			"plane_X0":"fixed",
			"plane_Y0":"sliding",
			"plane_Z0":"fixed",
			"plane_Xn":"fixed",
			"plane_Yn":"sliding",
			"plane_Zn":"fixed"
		}
	},
	"material":
	{
		"plastic":
		{
			"type":"mohr-coulomb",
			"id":1,
			"young":70e6,
			"density":2100,
			"poisson":0.3,
			"friction":20.0,
			"cohesion":1.0e3
		}
	},
	"body":
	{
		"soil":
		{
			"type":"polygon_2d",
			"extrude_direction":"y",
			"extrude_displacement":1,
			"discretization_length":1,
			"id":1,
			"points":
			[
				[  0, 0, 0 ],
				[110, 0, 0 ],
				[110, 0, 15],
				[ 50, 0, 15],
				[ 30, 0, 35],
				[  0, 0, 35]
			],
			"material_id":1
		}
	}
}

# Executable file names
executables = {"current": "MPM-Geomechanics"}

# Materials points in **thousands**
friction = [150, 250, 500] 

# Numbers of cohesion
cohesion = [1, 5, 10] 

CONFIG_FOLDER = "configuration-files"
RESULT_FOLDER = "results"
ARTIFACT_FOLDER = "artifacts"
LOGS_FOLDER = "logs"
BENCHMARK_CONFIGURATION_FILE_NAME = "start-multi-execution-config.json"
CACHE_FILE_NAME = "start-multi-execution-config-cached.json"

def read_flags():
    global clean_flag
    global cache_flag
    clean_flag = False
    cache_flag = False
    print("")
    arg = " ".join(sys.argv[1:])
    if arg == "--clean":
        print("> Clean flag detected (--clean)")
        clean_flag = True
    if arg == "--cache":
        print("> Cache flag detected (--cache)")
        cache_flag = True

# Configuration file name generator
def config_file (f, c):
    return f"config-f{f}-c{c}"

def create_folders():
    # get parameters from the console line
    if clean_flag:
        if Path(f"{RESULT_FOLDER}").exists():
            response = input(f"\n> The folder {RESULT_FOLDER} already exists. Do you want to delete it? (y/n): ")
            if response.lower() == "y":
                print(f"--> Deleting existing {RESULT_FOLDER} folder")
                shutil.rmtree(f"{RESULT_FOLDER}")
                print(f"--> Folder {RESULT_FOLDER} deleted")

    print("\n> Creating folders")
    Path(f"{RESULT_FOLDER}").mkdir(parents=True, exist_ok=True)
    Path(f"{RESULT_FOLDER}/{CONFIG_FOLDER}").mkdir(parents=True, exist_ok=True)
    Path(f"{RESULT_FOLDER}/{ARTIFACT_FOLDER}").mkdir(parents=True, exist_ok=True)
    Path(f"{RESULT_FOLDER}/{LOGS_FOLDER}").mkdir(parents=True, exist_ok=True)
    print(f"--> Folders created in {RESULT_FOLDER}")

def create_log_folder():
    for name in executables.keys():
        Path(f"{RESULT_FOLDER}/{LOGS_FOLDER}/{name}").mkdir(parents=True, exist_ok=True)

# Run a benchmark with a specific executable and configuration file
def run_benchmark(executable_path, name, config_file):
    print(f"----> [{name}] Running config file: {config_file}.json with executable: {executable_path}")
    try:
        log_reference = Path(f"{RESULT_FOLDER}/{LOGS_FOLDER}/{name}/{config_file}-{name}.log")
        config_path = Path(f"{RESULT_FOLDER}/{CONFIG_FOLDER}/{config_file}.json")

        exe_abs = os.path.abspath(executable_path)
        cfg_abs = os.path.abspath(config_path)

        Path(log_reference.parent).mkdir(parents=True, exist_ok=True)

        with open(log_reference, "w") as log_file:
            subprocess.run([exe_abs, str(cfg_abs)],
                           stdout=log_file,
                           stderr=subprocess.STDOUT,
                           check=True,
                           cwd=os.path.dirname(exe_abs))
    except Exception as e:
        print(f"----> [ERROR] An error occurred while running the benchmark: {e}")
        print(f"----> [ERROR] Executable: {executable_path} | name: {name} | Config File: {config_file}")

# Run all the benchmarks of a specific executable
def execute_benchmarks(executable_path, name):
  print(f"--> Starting executions: [{name}] ")
  for f in friction:
    for c in cohesion:
      run_benchmark(executable_path, name, config_file(f, c))
  print(f"--> Completed executions: [{name}]\n")

def create_configuration_files():
    print(f"\n> Creating configuration files")
    for f in friction:
        for c in cohesion:
            json_template["material"]["plastic"]["friction"] = f
            json_template["material"]["plastic"]["cohesion"] = c
            with open(f"{RESULT_FOLDER}/{CONFIG_FOLDER}/{config_file(f, c)}.json", "w") as file:
                json.dump(json_template, file, indent=4)
    print(f"--> Configuration files created in {RESULT_FOLDER}/{CONFIG_FOLDER}")

def read_configuration():
    global friction
    global cohesion
    global executables
    json_configuration = {}
    id_found = False

    if cache_flag and Path(f"{RESULT_FOLDER}/{CACHE_FILE_NAME}").is_file():
        print(f"\n> Reading cached configuration from {RESULT_FOLDER}/{CACHE_FILE_NAME}")
        with open(f"{RESULT_FOLDER}/{CACHE_FILE_NAME}", "r") as f:
            json_configuration = json.load(f)
        if "executables" in json_configuration:
            print("--> Cached executables found")
            executables = json_configuration["executables"]
            print("--> Cached executables loaded")
        if "parameters" in json_configuration:
            print("--> Cached parameters found")
            executables_parameters = json_configuration["parameters"]
            friction = executables_parameters["friction"] if "friction" in executables_parameters else friction
            cohesion = executables_parameters["cohesion"] if "cohesion" in executables_parameters else cohesion
            print(f"----> Friction: {friction}")
            print(f"----> Cohesion: {cohesion}")
        print(f"--> All parameters read successfully from cache")
        return
    elif cache_flag:
        print(f"--> [ERROR] Cached configuration file {RESULT_FOLDER}/{CACHE_FILE_NAME} not found. Reading from {BENCHMARK_CONFIGURATION_FILE_NAME}")
        raise

    print(f"\n> Reading configuration from {BENCHMARK_CONFIGURATION_FILE_NAME}")
    if not Path(BENCHMARK_CONFIGURATION_FILE_NAME).is_file():
        print(f"--> [WARNING] Configuration file '{BENCHMARK_CONFIGURATION_FILE_NAME}' not found. Using default parameters.")
        return

    with open(BENCHMARK_CONFIGURATION_FILE_NAME, "r") as f:
        json_configuration = json.load(f)

    # Read executables from configuration file
    if "executables" in json_configuration:
        print("--> Custom executables found in configuration file") 
        executables.clear()
        executables_list = json_configuration["executables"]
        for name, path in executables_list.items():
            if path.isdigit():
                print(f"----> Custom executable ID provided for [{name}]: {path}")
                id_found = True
            else:
                if not Path(path).is_file():
                    print(f"----> [ERROR] The provided path for [{name}] is not a valid file: {path}")
                    print(f"----> [ERROR] Please check the start-benchmark-configuration.json file")
                    raise
                print(f"----> Custom executable path provided for [{name}]: {path}")
            executables[name] = path

        # Verify GitHub CLI login status if any ID is found
        if id_found:
            try:
                print("--> Verifying GitHub CLI login status...")
                subprocess.run("gh auth status", shell=True, text=True, capture_output=True, check=True)
                print(f"----> GitHub CLI is logged in!")
            except Exception as e:
                print(f"----> [ERROR] GitHub CLI is not logged in. Please run 'gh auth login' to log in.")
                print(f"----> [ERROR] {e}")
                raise
            
        # Download executables from GitHub Actions using 'gh' CLI
        ARTIFACT_FILE_NAME = "MPM-Geomechanics"
        artifact_name = ""
        extension = ""
        repository = "fabricix/MPM-Geomechanics"
        if sys.platform == "win32":
            artifact_name = "MPM-Geomechanics-windows"
            extension = ".exe"

        if sys.platform == "linux" or sys.platform == "cygwin":
            artifact_name = "MPM-Geomechanics-linux"

        if artifact_name == "":
            print(f"----> [ERROR] Unsupported platform: {sys.platform}")
            raise

        for name, path in executables_list.items():
            if path.isdigit():
                print(f"\n----> Checking GitHub for run ID [{path}] for executable [{name}]...")
                try:
                    print(f"------> Checking if the run ID [{path}] exists in GitHub Actions (command: gh run view {path})...")
                    subprocess.run(f"gh run view {path} -R {repository}", shell=True, text=True, capture_output=True, check=True)
                    print(f"------> ID [{path}] exists")
                except Exception as e:
                    print(f"------> [ERROR] An error occurred while checking the run ID [{path}]")
                    print(f"------> [ERROR] Please check if the run ID [{path}] exists in GitHub Actions")
                    print(f"------> [ERROR] {e}")
                    raise

                try:
                    print(f"------> Creating folder for [{name}] in {RESULT_FOLDER}/{ARTIFACT_FOLDER}/{name}...")
                    Path(f"{RESULT_FOLDER}/{ARTIFACT_FOLDER}/{name}").mkdir(parents=True, exist_ok=True)

                    if Path(f"{RESULT_FOLDER}/{ARTIFACT_FOLDER}/{name}/{ARTIFACT_FILE_NAME}" + extension).is_file():
                        print(f"------> Executable already exists at {RESULT_FOLDER}/{ARTIFACT_FOLDER}/{name}/{ARTIFACT_FILE_NAME}" + extension + ". Skipping download of executable.")
                    else:
                        print(f"------> Downloading the executable for [{name}] to {RESULT_FOLDER}/{ARTIFACT_FOLDER} (command: gh run download {path} --name {artifact_name} -D {RESULT_FOLDER}/{ARTIFACT_FOLDER}/{name})...")
                        subprocess.run(f"gh run download {path} -R {repository} --name {artifact_name} -D {RESULT_FOLDER}/{ARTIFACT_FOLDER}/{name}", shell=True, text=True, capture_output=True, check=True)
                        print(f"------> Download completed for [{name}]")

                        if extension == ".exe":
                            print(f"------> Extracting .zip for [{name}]")
                            with zipfile.ZipFile(f"{RESULT_FOLDER}/{ARTIFACT_FOLDER}/{name}/{artifact_name}.zip", "r") as archivo_zip:
                                archivo_zip.extractall(f"{RESULT_FOLDER}/{ARTIFACT_FOLDER}/{name}")

                    # Set the executable path (example: benchmark/artifacts/current/MPM-Geomechanics <-- or MPM-Geomechanics.exe)
                    executables[name] = f"{RESULT_FOLDER}/{ARTIFACT_FOLDER}/{name}/{ARTIFACT_FILE_NAME}" + extension
                except Exception as e:
                    print(f"----> [ERROR] An error occurred while downloading executable for [{name}]")
                    print(f"----> [ERROR] Please check if the run ID [{path}] exists in GitHub Actions")
                    print(f"----> [ERROR] {e}")
                    raise
                
                    
    if "parameters" in json_configuration:
        print("\n--> Custom parameters found in configuration file")
        executables_parameters = json_configuration["parameters"]
        friction = executables_parameters["friction"] if "friction" in executables_parameters else friction
        cohesion = executables_parameters["cohesion"] if "cohesion" in executables_parameters else cohesion
        print(f"----> Friction: {friction}")
        print(f"----> Cohesion: {cohesion}")

    # Verify if executables exist
    if executables.values():
        print("\n--> Verifying executables paths")
        for name, path in executables.items():
            if not Path(path).is_file():
                print(f"----> [ERROR] The provided path for [{name}] is not a valid file: {path}")
                print(f"----> [ERROR] Please check the start-benchmark-configuration.json file")
                raise
        print ("----> All executables paths are valid")
        
    if executables.values():
        print("\n--> Executables to be used:")
        for name, path in executables.items():
            print(f"----> [{name}]: {path}")

    print(f"--> All parameters read successfully")

    # Save cached configuration
    print(f"\n--> Saving cached configuration to {CACHE_FILE_NAME}")
    with open(f"{RESULT_FOLDER}/{CACHE_FILE_NAME}", "w") as f:
        cache = {"executables": executables, "parameters": {"friction": friction, "cohesion": cohesion}}
        json.dump(cache, f, indent=4)
        print(f"----> Cached configuration saved to {RESULT_FOLDER}/{CACHE_FILE_NAME}")

def start_benchmarks():
    print("\n> Starting benchmarks")

    # Start time measurement
    start_time = time.time()

    # Create and start thread for each executable
    threads = []
    for name, executable_path in executables.items():
      thread = threading.Thread(target=execute_benchmarks, args=(executable_path, name))
      thread.start()
      threads.append(thread)

    for thread in threads:
      thread.join()

    # End time measurement
    end_time = time.time()
    elapsed_time = end_time - start_time
    print("--> All benchmarks completed")
    print(f"--> Check {RESULT_FOLDER}/{LOGS_FOLDER} for logs")
    print(f"--> Total elapsed time: {elapsed_time:.2f} seconds")

# Main function
def main():
    try: 
        # 1. Read command line flags
        read_flags()
        
        # 2. Create necessary folders
        create_folders()

        # 3. Read parameters from the console
        read_configuration()

        # 4. Create log folders
        create_log_folder()

        # 5. Create configuration files 
        create_configuration_files()

        # 6. Start benchmarking
        start_benchmarks()

        return 0
    except Exception as e:
        print(f"--> [ERROR] An error occurred during the process")
        print(f"--> [ERROR] {e}")
        return -1

# Start benchmarking process
main()