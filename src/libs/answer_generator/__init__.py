"""Answer Generator Module.

This package contains pluggable answer generation providers used to build
the generative Q&A layer (Phase 2) on top of retrieval:
- Base answer generator class + Answer data type
- Answer generator factory
- Implementations (Extractive / LLM / Template)
- NoneAnswerGenerator no-op for disabled generation
"""

from src.libs.answer_generator.answer_generator_factory import (
    AnswerGeneratorFactory,
)
from src.libs.answer_generator.base_answer_generator import (
    Answer,
    BaseAnswerGenerator,
    NoneAnswerGenerator,
    extract_citation_indices,
    sanitize_citation_markers,
)
from src.libs.answer_generator.extractive_answer_generator import (
    ExtractiveAnswerGenerator,
)
from src.libs.answer_generator.llm_answer_generator import LLMAnswerGenerator
from src.libs.answer_generator.template_answer_generator import (
    TemplateAnswerGenerator,
)

# Register providers (idempotent with the factory's top-level dict literal).
AnswerGeneratorFactory.register_provider("extractive", ExtractiveAnswerGenerator)
AnswerGeneratorFactory.register_provider("llm", LLMAnswerGenerator)
AnswerGeneratorFactory.register_provider("template", TemplateAnswerGenerator)

__all__ = [
    "Answer",
    "AnswerGeneratorFactory",
    "BaseAnswerGenerator",
    "NoneAnswerGenerator",
    "ExtractiveAnswerGenerator",
    "LLMAnswerGenerator",
    "TemplateAnswerGenerator",
    "extract_citation_indices",
    "sanitize_citation_markers",
]
