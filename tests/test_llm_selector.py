import pytest
from unittest.mock import patch, MagicMock
from typing import Optional, Dict, Any

from holmes.llm_selector import LLMSelector
from holmes.core.llm import LLM
from holmes.common.env_vars import (
    ROBUSTA_AI_MODEL_NAME_FALLBACK,
    ROBUSTA_API_ENDPOINT,
)


class MockLLM(LLM):
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.params = params if params is not None else {}

    def completion(self, prompt: str, temperature: float, max_tokens: int) -> str:
        return "mocked_completion"

    def embedding(self, text: str) -> list[float]:
        return [0.1, 0.2]


@pytest.fixture
def initial_api_key_fixture() -> str:
    return "test_initial_api_key"


@pytest.fixture
def model_list_config_fixture() -> Dict[str, Dict[str, Any]]:
    return {
        "model_one": {"model": "gpt-model-one", "api_key": "key_for_one"},
        "model_two": {"model": "gpt-model-two"},
        "model_three": {},
    }


@pytest.fixture
def default_model_from_config_fixture() -> str:
    return "default_config_model"


@pytest.fixture
def mock_holmes_info_fixture() -> MagicMock:
    mock_info = MagicMock()
    mock_info.robusta_ai_model_name = "robusta_specific_model"
    return mock_info


@pytest.fixture
def llm_selector_fixture(
    initial_api_key_fixture: str,
    model_list_config_fixture: Dict[str, Dict[str, Any]],
    default_model_from_config_fixture: str,
    mock_holmes_info_fixture: MagicMock,
) -> LLMSelector:
    return LLMSelector(
        initial_api_key=initial_api_key_fixture,
        model_list_config=model_list_config_fixture,
        default_model_from_config=default_model_from_config_fixture,
        holmes_info_object=mock_holmes_info_fixture,
    )


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
def test_select_llm_with_model_key_override_all(llm_selector_fixture: LLMSelector):
    llm = llm_selector_fixture.select_llm(model_key="model_one")
    assert isinstance(llm, MockLLM)
    assert llm.model_name == "gpt-model-one"
    assert llm.api_key == "key_for_one"
    assert llm.params == {}


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
def test_select_llm_with_model_key_uses_initial_api_key(
    llm_selector_fixture: LLMSelector, initial_api_key_fixture: str
):
    llm = llm_selector_fixture.select_llm(model_key="model_two")
    assert isinstance(llm, MockLLM)
    assert llm.model_name == "gpt-model-two"
    assert llm.api_key == initial_api_key_fixture
    assert llm.params == {}


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
def test_select_llm_with_model_key_uses_default_model_name(
    llm_selector_fixture: LLMSelector,
    default_model_from_config_fixture: str,
    initial_api_key_fixture: str,
):
    llm = llm_selector_fixture.select_llm(model_key="model_three")
    assert isinstance(llm, MockLLM)
    assert llm.model_name == default_model_from_config_fixture
    assert llm.api_key == initial_api_key_fixture
    assert llm.params == {}


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
def test_select_llm_with_default_model_from_config(
    initial_api_key_fixture: str,
    default_model_from_config_fixture: str,
    mock_holmes_info_fixture: MagicMock,
):
    selector = LLMSelector(
        initial_api_key=initial_api_key_fixture,
        model_list_config=None,
        default_model_from_config=default_model_from_config_fixture,
        holmes_info_object=mock_holmes_info_fixture,
    )
    llm = selector.select_llm()
    assert isinstance(llm, MockLLM)
    assert llm.model_name == default_model_from_config_fixture
    assert llm.api_key == initial_api_key_fixture
    assert llm.params == {}


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
def test_select_llm_with_first_in_model_list(
    initial_api_key_fixture: str,
    model_list_config_fixture: Dict[str, Dict[str, Any]],
    mock_holmes_info_fixture: MagicMock,
):
    selector = LLMSelector(
        initial_api_key=initial_api_key_fixture,
        model_list_config=model_list_config_fixture,
        default_model_from_config=None,
        holmes_info_object=mock_holmes_info_fixture,
    )
    llm = selector.select_llm()
    assert isinstance(llm, MockLLM)
    assert llm.model_name == "gpt-model-one"
    assert llm.api_key == "key_for_one"
    assert llm.params == {}


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
@patch("holmes.llm_selector.ROBUSTA_AI", True)
def test_select_llm_robusta_ai_fallback_success(
    initial_api_key_fixture: str, mock_holmes_info_fixture: MagicMock
):
    selector = LLMSelector(
        initial_api_key=initial_api_key_fixture,
        model_list_config=None,
        default_model_from_config=None,
        holmes_info_object=mock_holmes_info_fixture,
    )
    llm = selector.select_llm()
    assert isinstance(llm, MockLLM)
    assert llm.model_name == mock_holmes_info_fixture.robusta_ai_model_name
    assert llm.api_key == initial_api_key_fixture
    assert llm.params == {"base_url": ROBUSTA_API_ENDPOINT}


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
@patch("holmes.llm_selector.ROBUSTA_AI", True)
def test_select_llm_robusta_ai_fallback_uses_fallback_name(
    initial_api_key_fixture: str,
):
    mock_holmes_info_no_specific_name = MagicMock()
    del mock_holmes_info_no_specific_name.robusta_ai_model_name

    def mock_getattr_func(obj: Any, name: str, default: Any) -> Any:
        if name == "robusta_ai_model_name" and not hasattr(obj, name):
            return default
        return getattr(obj, name)

    with patch("holmes.llm_selector.getattr", mock_getattr_func):
        selector = LLMSelector(
            initial_api_key=initial_api_key_fixture,
            model_list_config=None,
            default_model_from_config=None,
            holmes_info_object=mock_holmes_info_no_specific_name,
        )
        llm = selector.select_llm()
        assert isinstance(llm, MockLLM)
        assert llm.model_name == ROBUSTA_AI_MODEL_NAME_FALLBACK
        assert llm.api_key == initial_api_key_fixture
        assert llm.params == {"base_url": ROBUSTA_API_ENDPOINT}


@patch("holmes.llm_selector.ROBUSTA_AI", True)
def test_select_llm_robusta_ai_fallback_no_api_key_raises_value_error(
    mock_holmes_info_fixture: MagicMock,
):
    selector = LLMSelector(
        initial_api_key=None,  # No API Key
        model_list_config=None,
        default_model_from_config=None,
        holmes_info_object=mock_holmes_info_fixture,
    )
    with pytest.raises(
        ValueError, match="ROBUSTA_AI is enabled but no API key is configured"
    ):
        selector.select_llm()


@patch("holmes.llm_selector.ROBUSTA_AI", True)
def test_select_llm_robusta_ai_fallback_no_holmes_info_raises_value_error(
    initial_api_key_fixture: str,
):
    selector = LLMSelector(
        initial_api_key=initial_api_key_fixture,
        model_list_config=None,
        default_model_from_config=None,
        holmes_info_object=None,
    )
    with pytest.raises(ValueError, match="holmes_info_object not available"):
        selector.select_llm()


@patch("holmes.llm_selector.ROBUSTA_AI", False)
def test_select_llm_no_configuration_raises_value_error():
    selector = LLMSelector(
        initial_api_key=None,
        model_list_config=None,
        default_model_from_config=None,
        holmes_info_object=None,
    )
    with pytest.raises(ValueError, match="No LLM model configuration provided"):
        selector.select_llm()


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
def test_select_llm_model_key_not_in_list_falls_back_to_default_config_model(
    llm_selector_fixture: LLMSelector,
    default_model_from_config_fixture: str,
    initial_api_key_fixture: str,
):
    llm = llm_selector_fixture.select_llm(model_key="unknown_model")
    assert isinstance(llm, MockLLM)
    assert llm.model_name == default_model_from_config_fixture
    assert llm.api_key == initial_api_key_fixture
    assert llm.params == {}


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
def test_select_llm_model_key_not_in_list_no_default_falls_back_to_first_in_list(
    initial_api_key_fixture: str,
    model_list_config_fixture: Dict[str, Dict[str, Any]],
    mock_holmes_info_fixture: MagicMock,
):
    selector = LLMSelector(
        initial_api_key=initial_api_key_fixture,
        model_list_config=model_list_config_fixture,
        default_model_from_config=None,
        holmes_info_object=mock_holmes_info_fixture,
    )
    llm = selector.select_llm(model_key="unknown_model")
    assert isinstance(llm, MockLLM)
    assert llm.model_name == "gpt-model-one"
    assert llm.api_key == "key_for_one"
    assert llm.params == {}


@patch("holmes.llm_selector.DefaultLLM", new=MockLLM)
@patch("holmes.llm_selector.ROBUSTA_AI", True)
def test_select_llm_empty_model_list_falls_back_to_robusta(
    initial_api_key_fixture: str, mock_holmes_info_fixture: MagicMock
):
    selector = LLMSelector(
        initial_api_key=initial_api_key_fixture,
        model_list_config={},
        default_model_from_config=None,
        holmes_info_object=mock_holmes_info_fixture,
    )
    llm = selector.select_llm()
    assert isinstance(llm, MockLLM)
    assert llm.model_name == mock_holmes_info_fixture.robusta_ai_model_name
    assert llm.api_key == initial_api_key_fixture
    assert llm.params == {"base_url": ROBUSTA_API_ENDPOINT}


@patch("holmes.llm_selector.ROBUSTA_AI", False)
def test_select_llm_no_model_name_determined_raises_error(initial_api_key_fixture: str):
    buggy_model_list = {"buggy_entry": {"api_key": "some_key"}}
    selector = LLMSelector(
        initial_api_key=initial_api_key_fixture,
        model_list_config=buggy_model_list,
        default_model_from_config=None,
        holmes_info_object=None,
    )
    with pytest.raises(
        ValueError, match="Could not determine an LLM model name to use."
    ):
        selector.select_llm(model_key="buggy_entry")
