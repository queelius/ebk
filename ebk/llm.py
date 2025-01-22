import os
import requests
from string import Template
from .config import load_ebkrc_config


def query_llm(lib_dir, prompt):
    """
    Queries an OpenAI-compatible LLM endpoint with the given prompt.

    :param prompt: The user query or conversation prompt text.
    :param model: The OpenAI model name to use, defaults to gpt-3.5-turbo.
    :param temperature: Sampling temperature, defaults to 0.7.
    :return: The JSON response from the endpoint.
    """
    endpoint, api_key, model = load_ebkrc_config()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # let's prefix the prompt with the contents of the file `llm-instructions.md`
    # however, since this is a ypi package, we need to find the path to the file
    # we can use the `__file__` variable to get the path to this file, and then
    # construct the path to the `llm-instructions.md` file
    file_instr_path = os.path.join(os.path.dirname(__file__), "llm-instructions.md")    

    # Read the markdown file
    with open(file_instr_path, "r") as f:
        template = Template(f.read())

    data = {
        "lib_dir": lib_dir
    }

    instructions = template.safe_substitute(data)
    prompt = instructions + "\n\Natural language query: " + prompt

    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(endpoint, headers=headers, json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        raise SystemError(f"Error calling LLM endpoint: {e}")
    except Exception as e:
        raise SystemError(f"Unknown Error: {e}")

    return response.json()