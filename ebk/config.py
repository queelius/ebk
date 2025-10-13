"""
Configuration management for EBK.

Handles loading and saving user configuration from:
- XDG config directory: ~/.config/ebk/config.json
- Fallback: ~/.ebk/config.json
- Legacy: ~/.ebkrc (for backward compatibility)
"""

import configparser
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "ollama"
    model: str = "llama3.2"
    host: str = "localhost"
    port: int = 11434
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None


@dataclass
class ServerConfig:
    """Web server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    auto_open_browser: bool = False
    page_size: int = 50


@dataclass
class CLIConfig:
    """CLI default options."""
    verbose: bool = False
    color: bool = True
    page_size: int = 50


@dataclass
class LibraryConfig:
    """Library-related settings."""
    default_path: Optional[str] = None


@dataclass
class EBKConfig:
    """Main EBK configuration."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    cli: CLIConfig = field(default_factory=CLIConfig)
    library: LibraryConfig = field(default_factory=LibraryConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "llm": asdict(self.llm),
            "server": asdict(self.server),
            "cli": asdict(self.cli),
            "library": asdict(self.library),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EBKConfig':
        """Create from dictionary."""
        llm_data = data.get("llm", {})
        server_data = data.get("server", {})
        cli_data = data.get("cli", {})
        library_data = data.get("library", {})
        return cls(
            llm=LLMConfig(**llm_data),
            server=ServerConfig(**server_data),
            cli=CLIConfig(**cli_data),
            library=LibraryConfig(**library_data),
        )


def get_config_path() -> Path:
    """
    Get configuration file path.

    Follows XDG Base Directory specification:
    1. $XDG_CONFIG_HOME/ebk/config.json (usually ~/.config/ebk/config.json)
    2. Fallback: ~/.ebk/config.json

    Returns:
        Path to config file
    """
    # Try XDG config directory first
    xdg_config_home = Path.home() / ".config"
    if xdg_config_home.exists():
        config_dir = xdg_config_home / "ebk"
    else:
        # Fallback to ~/.ebk
        config_dir = Path.home() / ".ebk"

    return config_dir / "config.json"


def load_config() -> EBKConfig:
    """
    Load configuration from file.

    Returns:
        EBKConfig instance with loaded values or defaults
    """
    config_path = get_config_path()

    if not config_path.exists():
        # Return default config
        return EBKConfig()

    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        return EBKConfig.from_dict(data)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Failed to load config from {config_path}: {e}")
        print("Using default configuration")
        return EBKConfig()


def save_config(config: EBKConfig) -> None:
    """
    Save configuration to file.

    Args:
        config: Configuration to save
    """
    config_path = get_config_path()

    # Create directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config
    with open(config_path, 'w') as f:
        json.dump(config.to_dict(), f, indent=2)

    print(f"Configuration saved to {config_path}")


def ensure_config_exists() -> Path:
    """
    Ensure configuration file exists, creating with defaults if not.

    Returns:
        Path to config file
    """
    config_path = get_config_path()

    if not config_path.exists():
        config = EBKConfig()
        save_config(config)
        print(f"Created default configuration at {config_path}")

    return config_path


def update_config(
    # LLM settings
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_host: Optional[str] = None,
    llm_port: Optional[int] = None,
    llm_api_key: Optional[str] = None,
    llm_temperature: Optional[float] = None,
    llm_max_tokens: Optional[int] = None,
    # Server settings
    server_host: Optional[str] = None,
    server_port: Optional[int] = None,
    server_auto_open: Optional[bool] = None,
    server_page_size: Optional[int] = None,
    # CLI settings
    cli_verbose: Optional[bool] = None,
    cli_color: Optional[bool] = None,
    cli_page_size: Optional[int] = None,
    # Library settings
    library_default_path: Optional[str] = None,
) -> None:
    """
    Update configuration.

    Only updates provided values, leaving others unchanged.
    """
    config = load_config()

    # Update LLM config
    if llm_provider is not None:
        config.llm.provider = llm_provider
    if llm_model is not None:
        config.llm.model = llm_model
    if llm_host is not None:
        config.llm.host = llm_host
    if llm_port is not None:
        config.llm.port = llm_port
    if llm_api_key is not None:
        config.llm.api_key = llm_api_key
    if llm_temperature is not None:
        config.llm.temperature = llm_temperature
    if llm_max_tokens is not None:
        config.llm.max_tokens = llm_max_tokens

    # Update server config
    if server_host is not None:
        config.server.host = server_host
    if server_port is not None:
        config.server.port = server_port
    if server_auto_open is not None:
        config.server.auto_open_browser = server_auto_open
    if server_page_size is not None:
        config.server.page_size = server_page_size

    # Update CLI config
    if cli_verbose is not None:
        config.cli.verbose = cli_verbose
    if cli_color is not None:
        config.cli.color = cli_color
    if cli_page_size is not None:
        config.cli.page_size = cli_page_size

    # Update library config
    if library_default_path is not None:
        config.library.default_path = library_default_path

    save_config(config)


# Backward compatibility
def update_llm_config(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    api_key: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> None:
    """Update LLM configuration (legacy function)."""
    update_config(
        llm_provider=provider,
        llm_model=model,
        llm_host=host,
        llm_port=port,
        llm_api_key=api_key,
        llm_temperature=temperature,
        llm_max_tokens=max_tokens,
    )


# Legacy support for ~/.ebkrc
def load_ebkrc_config():
    """
    Loads configuration from ~/.ebkrc (legacy).

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
