"""Tests for src/mostlyright/_internal/exceptions.py — error hierarchy.

TDD: Tests written FIRST. Implementation follows.
"""

from __future__ import annotations


class TestTherminalError:
    def test_base_error(self) -> None:
        from mostlyright._internal.exceptions import TherminalError

        err = TherminalError("boom")
        assert str(err) == "boom"
        assert err.status_code is None

    def test_base_error_with_status(self) -> None:
        from mostlyright._internal.exceptions import TherminalError

        err = TherminalError("boom", status_code=500)
        assert err.status_code == 500

    def test_is_exception(self) -> None:
        from mostlyright._internal.exceptions import TherminalError

        assert issubclass(TherminalError, Exception)


class TestNotFoundError:
    def test_default_message(self) -> None:
        from mostlyright._internal.exceptions import NotFoundError

        err = NotFoundError()
        assert err.status_code == 404
        assert "not found" in str(err).lower()

    def test_custom_message(self) -> None:
        from mostlyright._internal.exceptions import NotFoundError

        err = NotFoundError("Station ZZZ not found")
        assert "ZZZ" in str(err)
        assert err.status_code == 404


class TestRateLimitError:
    def test_default_retry_after(self) -> None:
        from mostlyright._internal.exceptions import RateLimitError

        err = RateLimitError()
        assert err.status_code == 429
        assert err.retry_after == 1

    def test_custom_retry_after(self) -> None:
        from mostlyright._internal.exceptions import RateLimitError

        err = RateLimitError(retry_after=60)
        assert err.retry_after == 60


class TestValidationError:
    def test_status_400(self) -> None:
        from mostlyright._internal.exceptions import ValidationError

        err = ValidationError("bad date")
        assert err.status_code == 400


class TestAuthenticationError:
    def test_status_401(self) -> None:
        from mostlyright._internal.exceptions import AuthenticationError

        err = AuthenticationError()
        assert err.status_code == 401


class TestForbiddenError:
    def test_status_403(self) -> None:
        from mostlyright._internal.exceptions import ForbiddenError

        err = ForbiddenError()
        assert err.status_code == 403


class TestServerError:
    def test_default_500(self) -> None:
        from mostlyright._internal.exceptions import ServerError

        err = ServerError()
        assert err.status_code == 500

    def test_custom_5xx(self) -> None:
        from mostlyright._internal.exceptions import ServerError

        err = ServerError("bad gateway", status_code=502)
        assert err.status_code == 502


class TestInheritance:
    def test_all_inherit_from_base(self) -> None:
        from mostlyright._internal.exceptions import (
            AuthenticationError,
            ForbiddenError,
            NotFoundError,
            RateLimitError,
            ServerError,
            TherminalError,
            ValidationError,
        )

        for cls in (
            NotFoundError,
            RateLimitError,
            ValidationError,
            AuthenticationError,
            ForbiddenError,
            ServerError,
        ):
            assert issubclass(cls, TherminalError)
