from openai import OpenAI
from config.localconfig import config


def get_openai_client() -> OpenAI:
    """
    Delivers configured OpenAI client
    ---------------------------------
    Input: None
    Output: OpenAI
    """
    api_key = config.get("gpt")
    if not api_key:
        raise ValueError("No OpenAI-API-Key set in config.")
    return OpenAI(api_key=api_key)
