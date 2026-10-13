import pytest

import matcher.gemini_scorer as gs


class _Err(Exception):
    def __init__(self, code):
        super().__init__(f"{code} error")
        self.code = code


class _Client:
    """generate_content fails per model with the given status code, else returns the model id."""

    def __init__(self, fail):
        self.fail, self.tried = fail, []
        self.models = self

    def generate_content(self, model, contents, config=None):
        self.tried.append(model)
        if model in self.fail:
            raise _Err(self.fail[model])
        return model


@pytest.fixture(autouse=True)
def two_models(monkeypatch):
    monkeypatch.setattr(gs, "MODELS", ["a", "b"])


@pytest.mark.parametrize("code", [404, 429, 503])
def test_model_specific_failure_cascades(code):
    c = _Client({"a": code})
    assert gs.generate(c, "p") == "b"
    assert c.tried == ["a", "b"]


@pytest.mark.parametrize("code", [400, 401, 403])
def test_key_or_request_error_does_not_cascade(code):
    c = _Client({"a": code})
    with pytest.raises(_Err):
        gs.generate(c, "p")
    assert c.tried == ["a"]


def test_all_models_failing_raises_last_error():
    c = _Client({"a": 404, "b": 429})
    with pytest.raises(_Err) as e:
        gs.generate(c, "p")
    assert e.value.code == 429  # the callers' 429 backoff still sees a quota error


def test_status_parsed_from_message_when_no_code_attr():
    assert gs._status_code(RuntimeError("404 NOT_FOUND. model gone")) == 404
    assert gs._status_code(RuntimeError("bad json")) is None


def test_scorer_uses_fallback_model_for_new_keys(monkeypatch):
    monkeypatch.setattr(gs, "_rpm_wait", lambda: None)

    class C(_Client):
        def generate_content(self, model, contents, config=None):
            self.tried.append(model)
            if model == "a":
                raise _Err(404)

            class R:
                text = '[{"score": 8, "reasoning": "ok", "flags": []}]'
            return R()

    c = C({})
    out = gs.score_jobs_batch([{"title": "DS", "company": "X", "location": "TLV", "description": ""}], "p", "cv", c)
    assert out[0]["score"] == 8 and c.tried == ["a", "b"]
