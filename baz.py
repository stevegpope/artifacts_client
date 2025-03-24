import logging
import subprocess
import time
import sys

# Get character and role from command line arguments
if len(sys.argv) != 3:
    print("Usage: python script.py <character> <role>")
    sys.exit(1)

character = sys.argv[1]
role = sys.argv[2]

# Set up logging
logging.basicConfig(filename=character + ".txt", level=logging.INFO, format="%(asctime)s - %(message)s")


# Define the path to the virtual environment's Python executable
python_executable = r"C:\Users\sarah\Desktop\code\.venv\Scripts\python.exe"

# Define the working directory
working_directory = r"C:\Users\sarah\Desktop\code\artifacts"

# Loop to run the program repeatedly
while True:
    try:
        logging.info(f"Starting the program with character={character}, role={role}...")

        # Define the program path and arguments as a list
        program_path = [python_executable, "main.py", "--character", character, "--role", role]
        
        # Run the program from the specified directory
        process = subprocess.Popen(program_path, cwd=working_directory)
        process.wait()  # Wait for the program to exit
        
        logging.info("Program finished. Waiting for 60 seconds before restarting...")

        # Wait for 60 seconds
        time.sleep(60)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        break  # Exit the loop on error
