import logging
import subprocess
import time
import sys
from collections import deque

# Get character and role from command line arguments
if len(sys.argv) != 3:
    print("Usage: python script.py <character> <role>")
    sys.exit(1)

character = sys.argv[1]
role = sys.argv[2]

# Set up logging
logging.basicConfig(
    filename=character + ".txt",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

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
        
        # Capture the last 200 lines of output using a deque
        last_lines = deque(maxlen=200)
        
        # Run the program from the specified directory
        with subprocess.Popen(
            program_path,
            cwd=working_directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        ) as process:
            for line in process.stdout:
                last_lines.append(line.strip())  # Store the latest 200 lines
                print(line, end="")  # Optional: show real-time output in terminal
        
            # Wait for the process to exit
            process.wait()

        # Log the last 200 lines after the program finishes
        logging.info("Program output (last 200 lines):")
        for line in last_lines:
            logging.info(line)
        
        logging.info("Program finished. Waiting for 60 seconds before restarting...")

        # Wait for 60 seconds
        time.sleep(60)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        break  # Exit the loop on error
