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
    monkeypatch.setattr(gs, "_cooldown_until", {})
    monkeypatch.setattr(gs, "_rpm_wait", lambda: None)
    monkeypatch.setattr(gs.time, "sleep", lambda s: None)


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


def test_busy_model_is_skipped_during_cooldown():
    c = _Client({"a": 503})
    assert gs.generate(c, "p") == "b"
    c.fail = {}  # "a" recovered, but it is still cooling down
    c.tried = []
    assert gs.generate(c, "p") == "b"
    assert c.tried == ["b"]  # no wasted call on the busy model


def test_cooling_models_are_still_tried_last():
    gs._cooldown_until.update({"a": gs.time.monotonic() + 999, "b": gs.time.monotonic() + 999})
    c = _Client({})
    assert gs.generate(c, "p") == "a"  # never dropped, just moved to the back


class _Resp:
    text = '[{"score": 7, "reasoning": "ok", "flags": []}]'


JOB = [{"title": "DS", "company": "X", "location": "TLV", "description": ""}]


def test_transient_5xx_on_every_model_is_retried():
    class C(_Client):
        calls = 0

        def generate_content(self, model, contents, config=None):
            C.calls += 1
            if C.calls <= 2:  # first attempt: both models 500
                raise _Err(500)
            return _Resp()

    assert gs.score_jobs_batch(JOB, "p", "cv", C({}))[0]["score"] == 7


def test_lasting_5xx_skips_the_jobs_instead_of_stopping_the_run():
    out = gs.score_jobs_batch(JOB, "p", "cv", _Client({"a": 500, "b": 503}))
    assert "scorer-error" in out[0]["flags"]  # not QuotaExhaustedError, which ends the whole run
