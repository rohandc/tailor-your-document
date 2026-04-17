import configparser
import os

# When set to True, the application will use provided test files and enable a "testing environment".
# Set to False for "production" use.

TESTING = False
if TESTING:
    openai_api_key_value = "fake-api-key"
    gemini_api_key_value = "fake-api-key"
    groq_api_key_value = "fake-api-key"
    dest_dir = "test"
else:
    dest_dir = "output"

    # Env vars take precedence (used in Docker / cloud deployments).
    # Fall back to config.ini for local dev.
    openai_api_key_value = os.environ.get("OPENAI_API_KEY", "")
    gemini_api_key_value = os.environ.get("GEMINI_API_KEY", "")
    groq_api_key_value = os.environ.get("GROQ_API_KEY", "")

    if os.path.exists("config.ini"):
        config = configparser.ConfigParser()
        config.read("config.ini")
        if not openai_api_key_value and "OPENAI" in config and "API_KEY" in config["OPENAI"]:
            openai_api_key_value = config.get("OPENAI", "API_KEY")
        if not gemini_api_key_value and "GEMINI" in config and "API_KEY" in config["GEMINI"]:
            gemini_api_key_value = config.get("GEMINI", "API_KEY")
        if not groq_api_key_value and "GROQ" in config and "API_KEY" in config["GROQ"]:
            groq_api_key_value = config.get("GROQ", "API_KEY")

if not os.path.exists(dest_dir):
    os.makedirs(dest_dir)
