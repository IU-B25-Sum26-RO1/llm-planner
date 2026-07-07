def get_system_prompt(file_path: str) -> str:
    """
    Reads the system prompt from the specified file and returns it as a string.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"System prompt file not found at {file_path}.")
        return ""
    except Exception as e:
        print(f"An error occurred while reading the system prompt: {e}")
        return ""
