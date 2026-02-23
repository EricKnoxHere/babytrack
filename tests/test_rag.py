"""Tests du pipeline RAG — indexation, retrieval, analyse.

Stratégie :
- MockEmbedding (LlamaIndex) pour tous les tests d'index/retrieval → zéro réseau
- Mock anthropic.Anthropic pour les tests analyzer → zéro API call
- Les tests d'intégration réels (modèle HF réel + Claude) sont tagués `integration`
  et nécessitent : pytest -m integration --run-integration
"""

import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.embeddings import MockEmbedding

from app.models.baby import Baby
from app.models.feeding import Feeding
from app.rag.indexer import build_index, load_index
from app.rag.retriever import format_context, retrieve_context
from app.rag.analyzer import analyze_feedings, _summarize_feedings

DOCS_DIR = Path("data/docs")
MOCK_EMBED_DIM = 384  # dimension simulée


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mock_embed_model():
    return MockEmbedding(embed_dim=MOCK_EMBED_DIM)


@pytest.fixture(scope="module")
def tmp_index_dir():
    d = tempfile.mkdtemp(prefix="babytrack_test_index_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="module")
def index(tmp_index_dir, mock_embed_model):
    """Index vectoriel construit avec MockEmbedding (pas de réseau)."""
    if not DOCS_DIR.exists() or not any(DOCS_DIR.iterdir()):
        pytest.skip("data/docs vide — skip tests RAG")
    with patch("app.rag.indexer._get_embed_model", return_value=mock_embed_model):
        return build_index(docs_dir=DOCS_DIR, index_dir=tmp_index_dir)


@pytest.fixture
def sample_baby() -> Baby:
    return Baby(
        id=1,
        name="Léa",
        birth_date=date(2026, 1, 1),
        birth_weight_grams=3200,
        created_at=datetime(2026, 1, 1, 9, 0, 0),
    )


@pytest.fixture
def sample_feedings(sample_baby) -> list[Feeding]:
    base = date(2026, 2, 23)
    return [
        Feeding(
            id=i + 1,
            baby_id=sample_baby.id,
            fed_at=datetime(base.year, base.month, base.day, 6 + i * 3, 0, 0),
            quantity_ml=120 + i * 10,
            feeding_type="bottle",
            created_at=datetime(base.year, base.month, base.day, 6 + i * 3, 1, 0),
        )
        for i in range(5)
    ]


# ─── Tests indexation ─────────────────────────────────────────────────────────

def test_build_index_creates_docstore(index, tmp_index_dir):
    """L'index construit doit persister un docstore.json."""
    assert (tmp_index_dir / "docstore.json").exists()


def test_load_index_from_cache(tmp_index_dir, mock_embed_model):
    """load_index doit charger depuis le cache sans reconstruire."""
    with patch("app.rag.indexer._get_embed_model", return_value=mock_embed_model):
        loaded = load_index(index_dir=tmp_index_dir)
    assert loaded is not None


def test_load_index_missing_raises(tmp_path):
    """load_index lève FileNotFoundError si l'index est absent."""
    with pytest.raises(FileNotFoundError, match="Index introuvable"):
        load_index(index_dir=tmp_path / "inexistant")


def test_build_index_force_rebuild(tmp_index_dir, mock_embed_model):
    """force_rebuild=True doit reconstruire même si l'index existe."""
    with patch("app.rag.indexer._get_embed_model", return_value=mock_embed_model):
        idx = build_index(docs_dir=DOCS_DIR, index_dir=tmp_index_dir, force_rebuild=True)
    assert idx is not None


# ─── Tests retrieval ──────────────────────────────────────────────────────────

def test_retrieve_context_returns_nodes(index, mock_embed_model):
    """Une query doit retourner au plus top_k passages."""
    with patch("app.rag.retriever.load_index", return_value=index), \
         patch("app.rag.indexer._get_embed_model", return_value=mock_embed_model):
        nodes = retrieve_context(
            query="volume recommandé biberon nourrisson 2 mois",
            top_k=3,
            index=index,
        )
    assert 0 < len(nodes) <= 3


def test_retrieve_context_documents_contain_text(index, mock_embed_model):
    """Les nodes récupérés doivent contenir du texte non vide."""
    with patch("app.rag.indexer._get_embed_model", return_value=mock_embed_model):
        nodes = retrieve_context(
            query="allaitement maternel recommandations",
            top_k=4,
            index=index,
        )
    assert all(len(n.text.strip()) > 0 for n in nodes)


def test_retrieve_context_docs_are_oms_or_sfp(index, mock_embed_model):
    """Les sources doivent provenir des guides OMS ou SFP."""
    with patch("app.rag.indexer._get_embed_model", return_value=mock_embed_model):
        nodes = retrieve_context(
            query="biberon volume fréquence nourrisson",
            top_k=4,
            index=index,
        )
    sources = [n.metadata.get("file_name", "") for n in nodes]
    assert any("oms" in s.lower() or "sfp" in s.lower() for s in sources), (
        f"Sources trouvées : {sources}"
    )


def test_format_context_empty():
    result = format_context([])
    assert "Aucun" in result


def test_format_context_contains_excerpt(index, mock_embed_model):
    with patch("app.rag.indexer._get_embed_model", return_value=mock_embed_model):
        nodes = retrieve_context(query="biberon", top_k=2, index=index)
    formatted = format_context(nodes)
    assert "Extrait" in formatted
    assert "score" in formatted


# ─── Tests résumé biberons ────────────────────────────────────────────────────

def test_summarize_feedings_empty():
    assert "Aucun biberon" in _summarize_feedings([])


def test_summarize_feedings_count(sample_feedings):
    result = _summarize_feedings(sample_feedings)
    assert "5" in result


def test_summarize_feedings_total_volume(sample_feedings):
    total = sum(f.quantity_ml for f in sample_feedings)
    assert str(total) in _summarize_feedings(sample_feedings)


def test_summarize_feedings_type_label(sample_feedings):
    result = _summarize_feedings(sample_feedings)
    assert "biberon" in result.lower()


def test_summarize_mixed_feedings(sample_baby):
    """Alimentation mixte (bottle + breastfeeding) doit afficher 'mixte'."""
    feedings = [
        Feeding(id=1, baby_id=1, fed_at=datetime(2026, 2, 23, 8), quantity_ml=100,
                feeding_type="bottle", created_at=datetime(2026, 2, 23, 8)),
        Feeding(id=2, baby_id=1, fed_at=datetime(2026, 2, 23, 11), quantity_ml=80,
                feeding_type="breastfeeding", created_at=datetime(2026, 2, 23, 11)),
    ]
    result = _summarize_feedings(feedings)
    assert "mixte" in result.lower()


# ─── Tests analyzer (mock Anthropic) ─────────────────────────────────────────

def _mock_claude_response(text: str = "### ✅ Tout va bien."):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=text)]
    mock_response.usage = MagicMock(output_tokens=42)
    return mock_response


def test_analyze_feedings_returns_string(sample_baby, sample_feedings, index):
    with patch("app.rag.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = _mock_claude_response()
        result = analyze_feedings(
            baby=sample_baby,
            feedings=sample_feedings,
            period_label="journée du 23/02/2026",
            index=index,
        )
    assert isinstance(result, str) and len(result) > 0


def test_analyze_feedings_prompt_has_baby_name(sample_baby, sample_feedings, index):
    """Le prompt envoyé à Claude doit contenir le nom du bébé."""
    captured = []

    def capture(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        return _mock_claude_response()

    with patch("app.rag.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.side_effect = capture
        analyze_feedings(baby=sample_baby, feedings=sample_feedings, index=index)

    assert captured and sample_baby.name in captured[0]


def test_analyze_feedings_empty_list(sample_baby, index):
    """analyzer ne doit pas planter si la liste de biberons est vide."""
    with patch("app.rag.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = _mock_claude_response(
            "Aucun biberon enregistré."
        )
        result = analyze_feedings(baby=sample_baby, feedings=[], index=index)
    assert isinstance(result, str)


def test_analyze_feedings_rag_failure_graceful(sample_baby, sample_feedings):
    """Si le RAG échoue, l'analyse doit quand même se faire (sans contexte)."""
    with patch("app.rag.analyzer.retrieve_context", side_effect=Exception("RAG KO")), \
         patch("app.rag.analyzer.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = _mock_claude_response()
        result = analyze_feedings(baby=sample_baby, feedings=sample_feedings)
    assert isinstance(result, str)
