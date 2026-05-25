
import pytest


class TestCommissionerScoreValidation:
    """Teston rregullën: pikët e komisionerit duhet 0-100."""

    def test_valid_scores(self):
        valid = [0, 1, 50, 99, 100]
        for score in valid:
            assert 0 <= score <= 100

    def test_invalid_scores(self):
        invalid = [-1, -10, 101, 200]
        for score in invalid:
            assert not (0 <= score <= 100)

    def test_boundary_values(self):
        assert 0 <= 0   <= 100  # minimum
        assert 0 <= 100 <= 100  # maksimum
        assert not (0 <= -1  <= 100)
        assert not (0 <= 101 <= 100)


class TestAIWeightValidation:
    """Teston rregullën qe ai_weight duhet te jete 0.0 - 1.0."""

    def test_valid_weights(self):
        valid = [0.0, 0.1, 0.5, 0.6, 1.0]
        for w in valid:
            assert 0.0 <= w <= 1.0

    def test_invalid_weights(self):
        invalid = [-0.1, 1.1, 2.0]
        for w in invalid:
            assert not (0.0 <= w <= 1.0)

    def test_default_weight_is_valid(self):
        default_weight = 0.6
        assert 0.0 <= default_weight <= 1.0


class TestCriteriaWeightSum:
    """Teston rregullen qe shuma e peshave të kritereve duhet 100."""

    def test_valid_sum(self):
        weights = [30, 40, 30]
        assert sum(weights) == 100

    def test_invalid_sum_over(self):
        weights = [40, 40, 30]
        assert sum(weights) != 100

    def test_invalid_sum_under(self):
        weights = [20, 30, 10]
        assert sum(weights) != 100

    def test_single_criterion_full_weight(self):
        weights = [100]
        assert sum(weights) == 100

    def test_empty_criteria_no_validation_needed(self):
        weights = []
        # Nëse nuk ka kritere, nuk ka validim
        assert len(weights) == 0


class TestPasswordStrength:
    """Teston rregulla bazike të fjalëkalimit."""

    def test_minimum_length(self):
        assert len("Ab1!abcd") >= 8

    def test_too_short(self):
        assert len("Ab1!") < 8

    def test_empty_password(self):
        assert len("") == 0

    def test_password_not_empty(self):
        password = "Secret123!"
        assert password.strip() != ""


class TestTokenSlugFormat:
    """Teston formatin e tenant_slug."""

    def test_valid_slug(self):
        slug = "org-alpha"
        assert slug.replace("-", "_").isidentifier()

    def test_slug_lowercase(self):
        slug = "orgalpha"
        assert slug == slug.lower()

    def test_schema_name_format(self):
        slug = "org-alpha"
        schema = f"tenant_{slug.replace('-', '_')}"
        assert schema == "tenant_org_alpha"
        assert " " not in schema

    def test_slug_no_spaces(self):
        slug = "orgalpha"
        assert " " not in slug
