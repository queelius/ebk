import configparser
import os

def load_ebkrc_config():
    """
    Loads configuration from ~/.ebkrc.

    The configuration file can contain various sections for different features.
    For example, [streamlit] section for dashboard configuration.
    """
    config_path = os.path.expanduser("~/.ebkrc")
    parser = configparser.ConfigParser()

    if not os.path.exists(config_path):
        # Config file is optional
        return parser

    parser.read(config_path)
    return parser
