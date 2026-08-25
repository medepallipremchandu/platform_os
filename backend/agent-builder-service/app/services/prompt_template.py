"""Minimal {{variable}} templating for agent prompts - deliberately not full Jinja2, so the
substitution rules an agent author needs to understand fit in one paragraph: every
{{name}} in system_prompt/user_prompt_template must appear in input_variables, and every
call to /invoke must supply exactly those variables."""
import re

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def extract_variables(*templates: str) -> list[str]:
    seen: list[str] = []
    for template in templates:
        for match in _PLACEHOLDER_RE.finditer(template):
            name = match.group(1)
            if name not in seen:
                seen.append(name)
    return seen


def render(template: str, variables: dict[str, str]) -> str:
    def _replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in variables:
            raise KeyError(name)
        return str(variables[name])

    return _PLACEHOLDER_RE.sub(_replace, template)
