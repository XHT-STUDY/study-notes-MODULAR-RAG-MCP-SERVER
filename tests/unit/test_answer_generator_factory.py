"""Unit tests for AnswerGeneratorFactory."""

from types import SimpleNamespace

import pytest

from src.core.settings import AnswerGeneratorSettings
from src.libs.answer_generator import (
    AnswerGeneratorFactory,
    ExtractiveAnswerGenerator,
    LLMAnswerGenerator,
    NoneAnswerGenerator,
    TemplateAnswerGenerator,
)


@pytest.mark.unit
class TestAnswerGeneratorFactory:
    """Tests for AnswerGeneratorFactory provider resolution and degradation."""

    def test_list_providers_includes_builtin(self) -> None:
        providers = AnswerGeneratorFactory.list_providers()
        assert "extractive" in providers
        assert "llm" in providers
        assert "template" in providers

    def test_create_extractive_from_full_settings(self) -> None:
        settings = SimpleNamespace(
            answer_generator=AnswerGeneratorSettings(
                enabled=True, provider="extractive"
            )
        )
        generator = AnswerGeneratorFactory.create(settings)
        assert isinstance(generator, ExtractiveAnswerGenerator)
        assert generator.is_enabled

    def test_create_llm_from_bare_settings(self) -> None:
        settings = AnswerGeneratorSettings(enabled=True, provider="llm")
        generator = AnswerGeneratorFactory.create(settings)
        assert isinstance(generator, LLMAnswerGenerator)

    def test_create_template(self) -> None:
        settings = SimpleNamespace(
            answer_generator=AnswerGeneratorSettings(
                enabled=True, provider="template"
            )
        )
        generator = AnswerGeneratorFactory.create(settings)
        assert isinstance(generator, TemplateAnswerGenerator)

    def test_create_provider_name_case_insensitive(self) -> None:
        settings = SimpleNamespace(
            answer_generator=AnswerGeneratorSettings(enabled=True, provider="Extractive")
        )
        generator = AnswerGeneratorFactory.create(settings)
        assert isinstance(generator, ExtractiveAnswerGenerator)

    def test_create_disabled_returns_none_generator(self) -> None:
        settings = SimpleNamespace(
            answer_generator=AnswerGeneratorSettings(
                enabled=False, provider="extractive"
            )
        )
        generator = AnswerGeneratorFactory.create(settings)
        assert isinstance(generator, NoneAnswerGenerator)
        assert not generator.is_enabled

    def test_create_none_provider_returns_none_generator(self) -> None:
        settings = SimpleNamespace(
            answer_generator=AnswerGeneratorSettings(enabled=True, provider="none")
        )
        generator = AnswerGeneratorFactory.create(settings)
        assert isinstance(generator, NoneAnswerGenerator)

    def test_create_unsupported_provider_raises(self) -> None:
        settings = SimpleNamespace(
            answer_generator=AnswerGeneratorSettings(enabled=True, provider="bogus")
        )
        with pytest.raises(ValueError, match="Unsupported AnswerGenerator provider"):
            AnswerGeneratorFactory.create(settings)

    def test_create_missing_section_raises(self) -> None:
        with pytest.raises(ValueError, match="answer_generator.provider"):
            AnswerGeneratorFactory.create(SimpleNamespace())

    def test_register_provider_rejects_non_subclass(self) -> None:
        class NotAGenerator:
            pass

        with pytest.raises(ValueError, match="must inherit"):
            AnswerGeneratorFactory.register_provider("bad", NotAGenerator)

    def test_register_provider_normalizes_case_and_creates(self) -> None:
        class CustomExtractive(ExtractiveAnswerGenerator):
            pass

        AnswerGeneratorFactory.register_provider("MyCustom", CustomExtractive)
        try:
            assert "mycustom" in AnswerGeneratorFactory.list_providers()
            settings = SimpleNamespace(
                answer_generator=AnswerGeneratorSettings(
                    enabled=True, provider="MYCUSTOM"
                )
            )
            assert isinstance(
                AnswerGeneratorFactory.create(settings), CustomExtractive
            )
        finally:
            AnswerGeneratorFactory._PROVIDERS.pop("mycustom", None)
