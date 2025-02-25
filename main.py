import argparse
from work.config import TOKEN
from work.worker import main_loop

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Run the program for a specific character.")
    parser.add_argument(
        "--character",
        type=str,
        required=True,
        help="The name of the character to run the program for."
    )
    args = parser.parse_args()

    # Use the provided character name
    character_name = args.character
    print(f"Starting program for character: {character_name}")

    # Pass the token and character name to the main loop
    main_loop(TOKEN, character_name)