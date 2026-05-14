import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.config import Config, get_config
from src.knowledge.loader import KnowledgeLoader


def _reset_config():
    Config._instance = None
    get_config.cache_clear()


def test_knowledge_loader_uses_sibling_wiki_by_default(monkeypatch):
    monkeypatch.delenv("SJAGENT_WIKI_PATH", raising=False)
    _reset_config()

    loader = KnowledgeLoader()

    expected = (Path(__file__).resolve().parents[2] / "sjwiki").resolve(strict=False)
    assert loader.base_path == expected


def test_knowledge_loader_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SJAGENT_WIKI_PATH", str(tmp_path))
    _reset_config()

    loader = KnowledgeLoader()

    assert loader.base_path == tmp_path.resolve(strict=False)
