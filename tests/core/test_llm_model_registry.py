import os
import tempfile
from typing import List
from unittest.mock import MagicMock, patch

import yaml
from pydantic import SecretStr

from holmes.config import Config
from holmes.core.llm import LLMModelRegistry
from holmes.core.supabase_dal import SupabaseDal


class TestLLMModelRegistry:
    """Test cases for LLMModelRegistry class focusing on _init_models method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_dal = MagicMock(spec=SupabaseDal)
        self.mock_dal.enabled = True
        self.mock_dal.account_id = "test-account"
        self.temp_files: List[str] = []  # Track temp files for cleanup

    def teardown_method(self) -> None:
        """Clean up temporary files."""
        for temp_file in self.temp_files:
            try:
                os.unlink(temp_file)
            except (OSError, FileNotFoundError):
                pass  # File might already be deleted
        self.temp_files = []

    def create_temp_model_file(self, model_data: dict) -> str:
        """Create a temporary model list file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        try:
            yaml.dump(model_data, temp_file)
            temp_file.flush()
            self.temp_files.append(temp_file.name)  # Track for cleanup
            return temp_file.name
        finally:
            temp_file.close()

    def test_init_models_existing_model_with_api_key_overwrites(self):
        """Test that existing model entry is overwritten when config.api_key is set."""
        # Create a model file with existing model
        model_data = {
            "test-model": {
                "model": "gpt-4",
                "api_key": "original-key",
                "api_base": "https://original.api.com",
                "api_version": "2023-01-01",
            }
        }
        temp_file = self.create_temp_model_file(model_data)

        with patch("holmes.core.llm.MODEL_LIST_FILE_LOCATION", temp_file), patch.object(
            LLMModelRegistry, "_should_load_robusta_ai", return_value=False
        ):
            # Create config with api_key set - this should trigger overwrite
            config = Config(
                model="test-model",
                api_key="new-key",
                api_base="https://new.api.com",
                api_version="2024-01-01",
            )

            registry = LLMModelRegistry(config, self.mock_dal)

            # Check that model entry was completely overwritten with new values
            model_entry = registry.models["test-model"]
            assert model_entry.model == "test-model"
            assert model_entry.name == "test-model"
            assert model_entry.api_key == SecretStr("new-key")
            assert model_entry.base_url == "https://new.api.com"
            assert model_entry.api_version == "2024-01-01"
            assert model_entry.is_robusta_model is False

    def test_init_models_existing_model_without_api_key_preserves(self):
        """Test that existing model entry is preserved when config.api_key is not set."""
        # Create a model file with existing model
        model_data = {
            "test-model": {
                "model": "gpt-4",
                "api_key": "original-key",
                "api_base": "https://original.api.com",
                "api_version": "2023-01-01",
                "is_robusta_model": True,
            }
        }
        temp_file = self.create_temp_model_file(model_data)

        with patch("holmes.core.llm.MODEL_LIST_FILE_LOCATION", temp_file), patch.object(
            LLMModelRegistry, "_should_load_robusta_ai", return_value=False
        ):
            # Create config without api_key - this should preserve existing model
            config = Config(
                model="test-model",
                api_key=None,  # No API key set
                api_base="https://new.api.com",  # These won't be used
                api_version="2024-01-01",  # These won't be used
            )

            registry = LLMModelRegistry(config, self.mock_dal)

            # Check that original model entry was preserved
            model_entry = registry.models["test-model"]
            assert model_entry.model == "gpt-4"  # Original value
            assert model_entry.api_key == SecretStr("original-key")  # Original value
            assert model_entry.api_base == "https://original.api.com"  # Original value
            assert model_entry.api_version == "2023-01-01"  # Original value
            assert model_entry.is_robusta_model is True  # Original value

    def test_init_models_nonexistent_model_creates_new_entry(self):
        """Test that new model entry is created when model doesn't exist in file."""
        # Create a model file without the target model
        model_data = {"other-model": {"model": "gpt-3.5", "api_key": "other-key"}}
        temp_file = self.create_temp_model_file(model_data)

        with patch("holmes.core.llm.MODEL_LIST_FILE_LOCATION", temp_file), patch.object(
            LLMModelRegistry, "_should_load_robusta_ai", return_value=False
        ):
            # Create config for a model that doesn't exist in file
            config = Config(
                model="new-model",
                api_base="https://new.api.com",
                api_key="new-key",
                api_version="2024-01-01",
            )

            registry = LLMModelRegistry(config, self.mock_dal)

            # Check that new model entry was created
            assert "new-model" in registry.models
            assert "other-model" in registry.models  # Original model should still exist

            new_model_entry = registry.models["new-model"]
            assert new_model_entry.model == "new-model"
            assert new_model_entry.name == "new-model"
            assert new_model_entry.base_url == "https://new.api.com"
            assert new_model_entry.api_key == SecretStr("new-key")
            assert new_model_entry.api_version == "2024-01-01"
            assert new_model_entry.is_robusta_model is False

    def test_init_models_nonexistent_model_without_api_key_still_creates(self):
        """Test that new model entry is created even without api_key when model doesn't exist."""
        # Create a model file without the target model
        model_data = {"other-model": {"model": "gpt-3.5", "api_key": "other-key"}}
        temp_file = self.create_temp_model_file(model_data)

        with patch("holmes.core.llm.MODEL_LIST_FILE_LOCATION", temp_file), patch.object(
            LLMModelRegistry, "_should_load_robusta_ai", return_value=False
        ):
            # Create config for nonexistent model without api_key
            config = Config(
                model="new-model",
                api_base="https://new.api.com",
                api_key=None,  # No API key
                api_version="2024-01-01",
            )

            registry = LLMModelRegistry(config, self.mock_dal)

            # Check that new model entry was still created (because not existing_model)
            assert "new-model" in registry.models

            new_model_entry = registry.models["new-model"]
            assert new_model_entry.model == "new-model"
            assert new_model_entry.name == "new-model"
            assert new_model_entry.base_url == "https://new.api.com"
            assert new_model_entry.api_key is None
            assert new_model_entry.api_version == "2024-01-01"
            assert new_model_entry.is_robusta_model is False
