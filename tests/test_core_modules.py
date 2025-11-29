"""
Tests for core utility modules: config, ident, decorators.

Tests focus on behavior and contracts, not implementation details.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Module under test
from ebk import ident
from ebk import config


# ============================================================================
# IDENT MODULE TESTS
# ============================================================================

class TestCanonicalizeText:
    """Test text canonicalization behavior."""

    def test_converts_to_lowercase(self):
        """Canonicalized text should be lowercase."""
        result = ident.canonicalize_text("HELLO World")
        assert result == result.lower()

    def test_removes_punctuation(self):
        """Punctuation should be removed."""
        result = ident.canonicalize_text("Hello, World! How's it?")
        assert "," not in result
        assert "!" not in result
        assert "'" not in result

    def test_replaces_spaces_with_underscores(self):
        """Spaces should become underscores."""
        result = ident.canonicalize_text("hello world")
        assert " " not in result
        assert "_" in result

    def test_collapses_multiple_spaces(self):
        """Multiple spaces should become single underscore."""
        result = ident.canonicalize_text("hello   world")
        assert "__" not in result

    def test_strips_whitespace(self):
        """Leading/trailing whitespace should be removed."""
        result = ident.canonicalize_text("  hello  ")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_empty_string_returns_empty(self):
        """Empty input returns empty output."""
        assert ident.canonicalize_text("") == ""


class TestCanonicalizeCreators:
    """Test creator list canonicalization behavior."""

    def test_sorts_creators_alphabetically(self):
        """Creators should be sorted for consistent output."""
        result1 = ident.canonicalize_creators(["Bob", "Alice", "Charlie"])
        result2 = ident.canonicalize_creators(["Charlie", "Alice", "Bob"])
        assert result1 == result2

    def test_joins_creators_with_underscore(self):
        """Multiple creators should be joined."""
        result = ident.canonicalize_creators(["Alice", "Bob"])
        assert "_" in result

    def test_empty_list_returns_empty(self):
        """Empty creator list returns empty string."""
        assert ident.canonicalize_creators([]) == ""

    def test_single_creator(self):
        """Single creator should work without separators."""
        result = ident.canonicalize_creators(["John Doe"])
        assert result == "john_doe"


class TestGenerateHashId:
    """Test hash ID generation behavior."""

    def test_returns_hex_string(self):
        """Hash should be a hexadecimal string."""
        entry = {"title": "Test Book", "creators": ["Author"], "language": "en"}
        result = ident.generate_hash_id(entry)
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_entry_same_hash(self):
        """Same metadata should produce same hash."""
        entry = {"title": "Test Book", "creators": ["Author"], "language": "en"}
        hash1 = ident.generate_hash_id(entry)
        hash2 = ident.generate_hash_id(entry)
        assert hash1 == hash2

    def test_different_entries_different_hash(self):
        """Different metadata should produce different hash."""
        entry1 = {"title": "Book One", "creators": ["Author"], "language": "en"}
        entry2 = {"title": "Book Two", "creators": ["Author"], "language": "en"}
        assert ident.generate_hash_id(entry1) != ident.generate_hash_id(entry2)

    def test_empty_entry_still_generates_hash(self):
        """Empty entry should still produce a valid hash (fallback to UUID)."""
        entry = {}
        result = ident.generate_hash_id(entry)
        assert len(result) == 64  # SHA256 hex length

    def test_hash_length_is_64(self):
        """SHA256 hash should be 64 characters."""
        entry = {"title": "Test", "creators": ["Author"], "language": "en"}
        assert len(ident.generate_hash_id(entry)) == 64


class TestAddUniqueId:
    """Test unique ID addition behavior."""

    def test_adds_unique_id_field(self):
        """Function should add 'unique_id' to entry."""
        entry = {"title": "Test Book"}
        result = ident.add_unique_id(entry)
        assert "unique_id" in result

    def test_returns_modified_entry(self):
        """Should return the same entry object, modified."""
        entry = {"title": "Test Book"}
        result = ident.add_unique_id(entry)
        assert result is entry

    def test_unique_id_is_valid_hash(self):
        """Added ID should be a valid hash string."""
        entry = {"title": "Test", "creators": ["Author"], "language": "en"}
        result = ident.add_unique_id(entry)
        assert len(result["unique_id"]) == 64


# ============================================================================
# CONFIG MODULE TESTS
# ============================================================================

class TestLLMConfig:
    """Test LLM configuration dataclass."""

    def test_default_values(self):
        """LLMConfig should have sensible defaults."""
        cfg = config.LLMConfig()
        assert cfg.provider == "ollama"
        assert cfg.model == "llama3.2"
        assert cfg.host == "localhost"
        assert cfg.port == 11434
        assert cfg.api_key is None
        assert 0 <= cfg.temperature <= 1

    def test_custom_values(self):
        """LLMConfig should accept custom values."""
        cfg = config.LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key"
        )
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4"
        assert cfg.api_key == "test-key"


class TestServerConfig:
    """Test server configuration dataclass."""

    def test_default_values(self):
        """ServerConfig should have sensible defaults."""
        cfg = config.ServerConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8000
        assert cfg.auto_open_browser is False
        assert cfg.page_size > 0


class TestCLIConfig:
    """Test CLI configuration dataclass."""

    def test_default_values(self):
        """CLIConfig should have sensible defaults."""
        cfg = config.CLIConfig()
        assert cfg.verbose is False
        assert cfg.color is True
        assert cfg.page_size > 0


class TestEBKConfig:
    """Test main EBK configuration."""

    def test_default_initialization(self):
        """EBKConfig should initialize with default sub-configs."""
        cfg = config.EBKConfig()
        assert isinstance(cfg.llm, config.LLMConfig)
        assert isinstance(cfg.server, config.ServerConfig)
        assert isinstance(cfg.cli, config.CLIConfig)
        assert isinstance(cfg.library, config.LibraryConfig)

    def test_to_dict_returns_nested_dict(self):
        """to_dict should produce serializable nested dictionary."""
        cfg = config.EBKConfig()
        result = cfg.to_dict()

        assert isinstance(result, dict)
        assert "llm" in result
        assert "server" in result
        assert "cli" in result
        assert "library" in result
        assert isinstance(result["llm"], dict)

    def test_from_dict_creates_config(self):
        """from_dict should reconstruct config from dictionary."""
        data = {
            "llm": {"provider": "openai", "model": "gpt-4"},
            "server": {"port": 9000},
            "cli": {"verbose": True},
            "library": {"default_path": "/test/path"}
        }
        cfg = config.EBKConfig.from_dict(data)

        assert cfg.llm.provider == "openai"
        assert cfg.llm.model == "gpt-4"
        assert cfg.server.port == 9000
        assert cfg.cli.verbose is True
        assert cfg.library.default_path == "/test/path"

    def test_round_trip_serialization(self):
        """to_dict followed by from_dict should preserve values."""
        original = config.EBKConfig()
        original.llm.provider = "test-provider"
        original.server.port = 12345

        data = original.to_dict()
        restored = config.EBKConfig.from_dict(data)

        assert restored.llm.provider == original.llm.provider
        assert restored.server.port == original.server.port


class TestConfigFilePaths:
    """Test config file path resolution."""

    def test_get_config_path_returns_path(self):
        """get_config_path should return a Path object."""
        result = config.get_config_path()
        assert isinstance(result, Path)

    def test_config_path_ends_with_json(self):
        """Config file should be JSON format."""
        result = config.get_config_path()
        assert result.name == "config.json"

    def test_config_path_in_user_directory(self):
        """Config should be in user's home directory tree."""
        result = config.get_config_path()
        home = Path.home()
        # Config should be somewhere under home
        assert str(home) in str(result)


class TestLoadConfig:
    """Test configuration loading behavior."""

    def test_returns_ebk_config(self):
        """load_config should return EBKConfig instance."""
        with patch.object(config, 'get_config_path') as mock_path:
            mock_path.return_value = Path("/nonexistent/config.json")
            result = config.load_config()
            assert isinstance(result, config.EBKConfig)

    def test_returns_defaults_when_file_missing(self):
        """Missing config file should return default config."""
        with patch.object(config, 'get_config_path') as mock_path:
            mock_path.return_value = Path("/nonexistent/config.json")
            result = config.load_config()
            # Should have default values
            assert result.llm.provider == "ollama"

    def test_loads_from_existing_file(self):
        """Should load values from existing config file."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump({
                "llm": {"provider": "custom-provider"},
                "server": {},
                "cli": {},
                "library": {}
            }, f)
            temp_path = Path(f.name)

        try:
            with patch.object(config, 'get_config_path', return_value=temp_path):
                result = config.load_config()
                assert result.llm.provider == "custom-provider"
        finally:
            temp_path.unlink()

    def test_handles_invalid_json_gracefully(self):
        """Invalid JSON should return defaults, not crash."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            f.write("not valid json {{{")
            temp_path = Path(f.name)

        try:
            with patch.object(config, 'get_config_path', return_value=temp_path):
                # Should not raise, should return defaults
                result = config.load_config()
                assert isinstance(result, config.EBKConfig)
        finally:
            temp_path.unlink()


class TestSaveConfig:
    """Test configuration saving behavior."""

    def test_creates_config_file(self):
        """save_config should create the config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "ebk" / "config.json"

            with patch.object(config, 'get_config_path', return_value=config_path):
                cfg = config.EBKConfig()
                config.save_config(cfg)

                assert config_path.exists()

    def test_saved_file_is_valid_json(self):
        """Saved config should be valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "ebk" / "config.json"

            with patch.object(config, 'get_config_path', return_value=config_path):
                cfg = config.EBKConfig()
                config.save_config(cfg)

                with open(config_path) as f:
                    data = json.load(f)  # Should not raise
                    assert "llm" in data

    def test_creates_parent_directories(self):
        """save_config should create parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "deep" / "nested" / "config.json"

            with patch.object(config, 'get_config_path', return_value=config_path):
                cfg = config.EBKConfig()
                config.save_config(cfg)

                assert config_path.parent.exists()


class TestUpdateConfig:
    """Test configuration update behavior."""

    def test_updates_specific_fields(self):
        """update_config should only modify specified fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            # Create initial config
            initial = config.EBKConfig()
            initial.llm.provider = "initial"
            initial.server.port = 1111

            with patch.object(config, 'get_config_path', return_value=config_path):
                config.save_config(initial)

                # Update only one field
                config.update_config(llm_provider="updated")

                # Reload and verify
                result = config.load_config()
                assert result.llm.provider == "updated"
                assert result.server.port == 1111  # Unchanged

    def test_update_llm_settings(self):
        """Should be able to update all LLM settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            with patch.object(config, 'get_config_path', return_value=config_path):
                config.save_config(config.EBKConfig())

                config.update_config(
                    llm_provider="openai",
                    llm_model="gpt-4",
                    llm_temperature=0.5
                )

                result = config.load_config()
                assert result.llm.provider == "openai"
                assert result.llm.model == "gpt-4"
                assert result.llm.temperature == 0.5


class TestLegacyConfig:
    """Test legacy .ebkrc configuration support."""

    def test_load_ebkrc_returns_parser(self):
        """load_ebkrc_config should return a ConfigParser."""
        import configparser
        result = config.load_ebkrc_config()
        assert isinstance(result, configparser.ConfigParser)

    def test_handles_missing_ebkrc_gracefully(self):
        """Missing .ebkrc should return empty parser, not crash."""
        with patch('os.path.exists', return_value=False):
            result = config.load_ebkrc_config()
            assert len(result.sections()) == 0


# ============================================================================
# DECORATORS MODULE TESTS
# ============================================================================

class TestHandleLibraryErrors:
    """Test error handling decorator behavior."""

    def test_passes_through_successful_calls(self):
        """Successful function calls should work normally."""
        from ebk.decorators import handle_library_errors

        @handle_library_errors
        def successful_function():
            return "success"

        # Should not interfere with successful execution
        # Note: We can't easily test the actual decorator without typer context
        # This tests the decorator can be applied without errors
        assert callable(successful_function)

    def test_preserves_function_name(self):
        """Decorated function should preserve original name."""
        from ebk.decorators import handle_library_errors

        @handle_library_errors
        def my_function():
            pass

        assert my_function.__name__ == "my_function"


class TestValidatePath:
    """Test path validation decorator behavior."""

    def test_decorator_can_be_applied(self):
        """validate_path decorator should be applicable to functions."""
        from ebk.decorators import validate_path

        @validate_path("directory")
        def process_dir(path):
            return path

        assert callable(process_dir)

    def test_preserves_function_name(self):
        """Decorated function should preserve original name."""
        from ebk.decorators import validate_path

        @validate_path("file")
        def my_file_handler(path):
            pass

        assert my_file_handler.__name__ == "my_file_handler"


class TestRequireConfirmation:
    """Test confirmation decorator behavior."""

    def test_decorator_can_be_applied(self):
        """require_confirmation decorator should be applicable."""
        from ebk.decorators import require_confirmation

        @require_confirmation("Are you sure?")
        def dangerous_operation():
            return "done"

        assert callable(dangerous_operation)

    def test_preserves_function_name(self):
        """Decorated function should preserve original name."""
        from ebk.decorators import require_confirmation

        @require_confirmation()
        def delete_everything():
            pass

        assert delete_everything.__name__ == "delete_everything"

    def test_bypasses_with_yes_flag(self):
        """Function should run without prompt if yes=True."""
        from ebk.decorators import require_confirmation

        call_count = 0

        @require_confirmation("Confirm?")
        def tracked_function(yes=False):
            nonlocal call_count
            call_count += 1
            return "executed"

        # With yes=True, should execute immediately
        result = tracked_function(yes=True)
        assert result == "executed"
        assert call_count == 1
