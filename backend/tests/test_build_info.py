from backend.app.build_info import get_build_info


def test_build_identity_precedence_and_unknown(monkeypatch):
    for name in ("APP_BUILD_SHA", "RENDER_GIT_COMMIT", "GITHUB_SHA"):
        monkeypatch.delenv(name, raising=False)
    assert get_build_info() == {"commit_sha": None, "source": "unknown"}
    monkeypatch.setenv("APP_BUILD_SHA", "unknown")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "a" * 40)
    assert get_build_info() == {"commit_sha": "a" * 40, "source": "RENDER_GIT_COMMIT"}
    monkeypatch.setenv("APP_BUILD_SHA", "B" * 40)
    assert get_build_info() == {"commit_sha": "b" * 40, "source": "APP_BUILD_SHA"}


def test_build_identity_does_not_publish_arbitrary_environment_values(monkeypatch):
    monkeypatch.setenv("APP_BUILD_SHA", "https://name:secret@example.com")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "bad-value")
    monkeypatch.setenv("GITHUB_SHA", "short-sha")
    assert get_build_info() == {"commit_sha": None, "source": "unknown"}
