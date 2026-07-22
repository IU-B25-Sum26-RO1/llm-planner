def get_system_prompt(file_path: str, logger=None) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        if logger:
            logger.error(f"System prompt file not found at {file_path}.")
        else:
            print(f"System prompt file not found at {file_path}.")
        return ""
    except Exception as e:
        if logger:
            logger.error(f"An error occurred while reading the system prompt: {e}")
        else:
            print(f"An error occurred while reading the system prompt: {e}")
        return ""
