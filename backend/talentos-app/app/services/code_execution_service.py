"""Executes a candidate's code submission against a question's test cases and compares
stdout to the expected output - the same input/output matching model real coding-judge
platforms (HackerRank, LeetCode, etc.) use.

SECURITY NOTE: this runs candidate-submitted code as a plain OS subprocess with a wall-clock
timeout and no other isolation (no network/filesystem/memory sandboxing, no container). That
is acceptable for an internal, API-key-gated assessment tool exercised by trusted recruiters
and candidates, but it is NOT safe to expose to untrusted/public traffic as-is. For a public
or multi-tenant deployment, run this inside a locked-down container (no network, read-only
filesystem, CPU/memory limits, e.g. gVisor/Firecracker/Docker with --network=none) instead of
a bare subprocess.
"""

import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import InvalidStateError
from app.models.question import QuestionTestCase

logger = logging.getLogger("app.services.code_execution")

_RUNNERS = {
    "python": {"command": [sys.executable], "extension": ".py"},
    "javascript": {"command": ["node"], "extension": ".js"},
}


@dataclass
class TestCaseExecutionResult:
    test_case: QuestionTestCase
    actual_output: str
    passed: bool
    stderr: str | None
    execution_time_ms: float


def supported_languages() -> list[str]:
    return list(_RUNNERS.keys())


def run_test_cases(
    language: str,
    code: str,
    test_cases: list[QuestionTestCase],
    timeout_seconds: float,
    max_output_chars: int,
) -> list[TestCaseExecutionResult]:
    runner = _RUNNERS.get(language)
    if runner is None:
        raise InvalidStateError(
            f"Unsupported language '{language}'. Supported: {', '.join(supported_languages())}"
        )

    results: list[TestCaseExecutionResult] = []
    with tempfile.TemporaryDirectory(prefix="talentos_code_") as tmp_dir:
        code_path = Path(tmp_dir) / f"solution{runner['extension']}"
        code_path.write_text(code, encoding="utf-8")
        command = [*runner["command"], str(code_path)]

        for test_case in test_cases:
            start = time.perf_counter()
            try:
                proc = subprocess.run(
                    command,
                    input=test_case.input,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                actual_output = proc.stdout.strip()[:max_output_chars]
                stderr = (proc.stderr.strip()[:max_output_chars] or None) if proc.returncode != 0 else None
                passed = proc.returncode == 0 and actual_output == test_case.expected_output.strip()
            except subprocess.TimeoutExpired:
                actual_output = ""
                stderr = f"Execution timed out after {timeout_seconds}s"
                passed = False
            except FileNotFoundError:
                logger.error("Runtime for language '%s' not found on PATH (command=%s)", language, command[0])
                actual_output = ""
                stderr = f"Runtime for '{language}' is not available on this server"
                passed = False

            results.append(
                TestCaseExecutionResult(
                    test_case=test_case,
                    actual_output=actual_output,
                    passed=passed,
                    stderr=stderr,
                    execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
                )
            )

    return results
