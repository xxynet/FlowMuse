"""Named workflow variables and single-pass prompt interpolation."""
import re

MAX_VARIABLES = 50
MAX_VARIABLE_TEXT = 32000
VARIABLE_NAME = r"[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff-]{0,63}"
PLACEHOLDER = re.compile(
    rf"(?<!\{{)(?:\{{\{{\s*({VARIABLE_NAME})\s*\}}\}}|\{{\s*({VARIABLE_NAME})\s*\}})(?!\}})"
)


class TemplateError(ValueError):
    """Safe validation messages; variable values must never appear in errors."""


def merge_variables(inherited: dict[str, str], own: dict[str, str]) -> dict[str, str]:
    result = {**inherited, **own}
    if len(result) > MAX_VARIABLES or sum(len(value) for value in result.values()) > MAX_VARIABLE_TEXT:
        raise TemplateError("变量数量或内容超过限制（最多 50 个变量、合计 32000 字符）")
    return result


def resolve_template(value: str, text: str = "", variables: dict[str, str] | None = None) -> str:
    context = {"text": text, **(variables or {})}
    expanded_length, previous_end = 0, 0

    def replace(match):
        nonlocal expanded_length, previous_end
        name = match[1] or match[2]
        if name not in context:
            raise TemplateError(f"未定义变量：{name}，请连接变量设置节点并检查变量名")
        replacement = context[name]
        expanded_length += match.start() - previous_end + len(replacement)
        previous_end = match.end()
        if expanded_length > MAX_VARIABLE_TEXT:
            raise TemplateError("替换变量后的提示词超过 32000 字符")
        return replacement

    result = PLACEHOLDER.sub(replace, value).strip()
    if len(result) > MAX_VARIABLE_TEXT:
        raise TemplateError("替换变量后的提示词超过 32000 字符")
    return result
