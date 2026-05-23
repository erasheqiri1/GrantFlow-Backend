"""
Unit teste për funksionet e ai_scoring service.
Testohen funksionet pa DB dhe pa thirrje AI.
"""
import pytest
from unittest.mock import MagicMock
from app.services.ai_scoring import _heuristic_score, _build_prompt, _get_client


# ──────────────────────────────────────────────
# Helper: mock objekte për teste
# ──────────────────────────────────────────────
def make_app(motivation_letter="Kjo eshte nje leter motivuese e shkruar mire per grantin."):
    app = MagicMock()
    app.motivation_letter = motivation_letter
    return app


def make_answer(text):
    a = MagicMock()
    a.answer_text = text
    return a


def make_criterion(name="Kriteri 1", weight=0.5, is_required=True):
    c = MagicMock()
    c.name = name
    c.weight = weight
    c.is_required = is_required
    return c


def make_grant(title="Grant Test", description="Pershkrim i grantit"):
    g = MagicMock()
    g.title = title
    g.description = description
    return g


# ──────────────────────────────────────────────
# Teste për _heuristic_score
# ──────────────────────────────────────────────
class TestHeuristicScore:
    def test_returns_tuple(self):
        app = make_app()
        score, justification = _heuristic_score(app, [], [])
        assert isinstance(score, float)
        assert isinstance(justification, str)

    def test_score_between_0_and_100(self):
        app = make_app()
        answers = [make_answer("Pergjigje e detajuar per pyetjen.")]
        criteria = [make_criterion()]
        score, _ = _heuristic_score(app, answers, criteria)
        assert 0 <= score <= 100

    def test_longer_motivation_gives_higher_score(self):
        short_app = make_app("Shpres.")
        long_app  = make_app("A" * 1000)
        answers   = []
        criteria  = []

        short_score, _ = _heuristic_score(short_app, answers, criteria)
        long_score,  _ = _heuristic_score(long_app,  answers, criteria)
        assert long_score >= short_score

    def test_no_motivation_letter(self):
        app = make_app(motivation_letter=None)
        score, justification = _heuristic_score(app, [], [])
        assert score >= 0
        assert "Mungon letra motivuese" in justification

    def test_all_answers_filled_increases_score(self):
        app_no_ans  = make_app()
        app_with_ans = make_app()
        answers = [make_answer("Pergjigje") for _ in range(5)]

        score_no,   _ = _heuristic_score(app_no_ans,  [],      [])
        score_with, _ = _heuristic_score(app_with_ans, answers, [])
        assert score_with >= score_no

    def test_empty_answers_dont_crash(self):
        app = make_app()
        answers = [make_answer(""), make_answer(None)]
        score, _ = _heuristic_score(app, answers, [])
        assert 0 <= score <= 100

    def test_justification_contains_score(self):
        app = make_app()
        score, justification = _heuristic_score(app, [], [])
        assert "heuristike" in justification


# ──────────────────────────────────────────────
# Teste për _build_prompt
# ──────────────────────────────────────────────
class TestBuildPrompt:
    def test_returns_string(self):
        app     = make_app()
        grant   = make_grant()
        prompt  = _build_prompt(app, grant, [], [])
        assert isinstance(prompt, str)

    def test_contains_grant_title(self):
        app    = make_app()
        grant  = make_grant(title="Grant per Arsim")
        prompt = _build_prompt(app, grant, [], [])
        assert "Grant per Arsim" in prompt

    def test_contains_motivation_letter(self):
        app    = make_app(motivation_letter="Motivimi im i forte.")
        grant  = make_grant()
        prompt = _build_prompt(app, grant, [], [])
        assert "Motivimi im i forte." in prompt

    def test_contains_criteria(self):
        app      = make_app()
        grant    = make_grant()
        criteria = [make_criterion(name="Eksperienca")]
        prompt   = _build_prompt(app, grant, criteria, [])
        assert "Eksperienca" in prompt

    def test_contains_answers(self):
        app     = make_app()
        grant   = make_grant()
        answers = [make_answer("Pergjigja ime e detajuar.")]
        prompt  = _build_prompt(app, grant, [], answers)
        assert "Pergjigja ime e detajuar." in prompt

    def test_no_criteria_shows_fallback_message(self):
        app    = make_app()
        grant  = make_grant()
        prompt = _build_prompt(app, grant, [], [])
        assert "Nuk ka kritere specifike" in prompt

    def test_doc_texts_included(self):
        app    = make_app()
        grant  = make_grant()
        prompt = _build_prompt(app, grant, [], [], doc_texts=["[CV.pdf]\nPermbajtja e CV-se."])
        assert "DOKUMENTET E NGARKUARA" in prompt
        assert "CV.pdf" in prompt

    def test_no_doc_texts_no_section(self):
        app    = make_app()
        grant  = make_grant()
        prompt = _build_prompt(app, grant, [], [], doc_texts=None)
        assert "DOKUMENTET E NGARKUARA" not in prompt

    def test_ends_with_instruction(self):
        app    = make_app()
        grant  = make_grant()
        prompt = _build_prompt(app, grant, [], [])
        assert "0-100" in prompt

    def test_null_grant_handled(self):
        app    = make_app()
        prompt = _build_prompt(app, None, [], [])
        assert "Pa titull" in prompt

    def test_motivation_truncated_at_1000_chars(self):
        app   = make_app(motivation_letter="A" * 2000)
        grant = make_grant()
        prompt = _build_prompt(app, grant, [], [])
        # Letra nuk duhet të kalojë 1000 karaktere brenda prompt-it
        assert "A" * 1001 not in prompt


# ──────────────────────────────────────────────
# Teste për final_score formula
# ──────────────────────────────────────────────
class TestFinalScoreFormula:
    """Teston formulën: final = ai * ai_weight + commissioner * (1 - ai_weight)"""

    def test_equal_weights(self):
        ai_score    = 80.0
        comm_score  = 60.0
        ai_weight   = 0.5
        final = round(ai_score * ai_weight + comm_score * (1 - ai_weight), 2)
        assert final == 70.0

    def test_full_ai_weight(self):
        ai_score   = 90.0
        comm_score = 50.0
        ai_weight  = 1.0
        final = round(ai_score * ai_weight + comm_score * (1 - ai_weight), 2)
        assert final == 90.0

    def test_full_commissioner_weight(self):
        ai_score   = 90.0
        comm_score = 40.0
        ai_weight  = 0.0
        final = round(ai_score * ai_weight + comm_score * (1 - ai_weight), 2)
        assert final == 40.0

    def test_default_weight_60_40(self):
        ai_score   = 100.0
        comm_score = 0.0
        ai_weight  = 0.6
        final = round(ai_score * ai_weight + comm_score * (1 - ai_weight), 2)
        assert final == 60.0

    def test_final_score_within_bounds(self):
        for ai in [0, 50, 100]:
            for comm in [0, 50, 100]:
                for w in [0.0, 0.5, 1.0]:
                    final = ai * w + comm * (1 - w)
                    assert 0 <= final <= 100


# ──────────────────────────────────────────────
# Teste për _get_client
# ──────────────────────────────────────────────
class TestGetClient:
    def test_returns_tuple(self):
        client, model = _get_client()
        assert isinstance(model, str)

    def test_no_api_key_returns_heuristic(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "")
        monkeypatch.setattr(config.settings, "GROQ_API_KEY", "")
        client, model = _get_client()
        assert client is None
        assert model == "heuristic-fallback"
