#!/usr/bin/env python3

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set
import tokenize

SAFE_EXCLUDED_DIRNAMES = {
    ".git",
    "venv",
    ".venv",
    "env",
    ".env",
    "build",
    "dist",
    "node_modules",
}

DEFAULT_KEEP_COMMENT_KEYWORDS = {

    "noqa",
    "type: ignore",
    "fmt: off",
    "fmt: on",
    "isort: skip",
    "pylint",
    "pragma",
    "pyright:",
    "mypy:",
    "coding:",
}

DEFAULT_KEEP_SHELL_COMMENT_KEYWORDS = {
    "shellcheck",
}

ENCODING_COOKIE_RE = re.compile(r"coding[:=]\s*([-\.\w]+)")

PYTHON_CACHE_PATTERNS = {
    "__pycache__",
    "htmlcov",
}

def remove_python_cache(paths: List[Path]) -> int:
    removed_count = 0

    for root_path in paths:
        if not root_path.exists():
            continue

        cache_dirs_to_remove = set()
        cache_files_to_remove = []

        for dirpath, dirnames, filenames in os.walk(root_path):

            if any(excluded in Path(dirpath).parts for excluded in SAFE_EXCLUDED_DIRNAMES if excluded != "__pycache__"):
                continue

            for dirname in list(dirnames):
                if (dirname in PYTHON_CACHE_PATTERNS or
                    dirname.startswith('.pytest_cache') or
                    dirname.startswith('.mypy_cache') or
                    dirname == 'htmlcov' or
                    dirname.startswith('.tox')):
                    cache_path = Path(dirpath) / dirname
                    cache_dirs_to_remove.add(cache_path)
                    dirnames.remove(dirname)

            for filename in filenames:
                if (filename.endswith(('.pyc', '.pyo', '.pyd')) or
                    filename == '.coverage' or
                    filename.startswith('.coverage.') or
                    filename == '.pytest_cache'):
                    cache_file = Path(dirpath) / filename
                    cache_files_to_remove.append(cache_file)

    for cache_path in cache_dirs_to_remove:
        try:
            shutil.rmtree(cache_path)
            print(f"[INFO] Удалено: {cache_path}")
            removed_count += 1
        except Exception as e:
            print(f"[WARN] Не удалось удалить {cache_path}: {e}", file=sys.stderr)

    for cache_file in cache_files_to_remove:
        try:
            cache_file.unlink()
            print(f"[INFO] Удалено: {cache_file}")
            removed_count += 1
        except Exception as e:
            print(f"[WARN] Не удалось удалить {cache_file}: {e}", file=sys.stderr)

    return removed_count

def discover_source_files(paths: List[Path]) -> Dict[str, List[Path]]:
    discovered: Dict[str, List[Path]] = {"py": [], "sh": []}
    for root_path in paths:
        if root_path.is_file():
            if root_path.suffix == ".py":
                discovered["py"].append(root_path)
            elif root_path.suffix == ".sh":
                discovered["sh"].append(root_path)
            continue
        if not root_path.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [
                d for d in dirnames if d not in SAFE_EXCLUDED_DIRNAMES
                and d != "__pycache__" and not d.startswith(".")
            ]
            for filename in filenames:
                if filename.endswith(".py"):
                    discovered["py"].append(Path(dirpath) / filename)
                elif filename.endswith(".sh"):
                    discovered["sh"].append(Path(dirpath) / filename)
    return discovered

def has_shebang(line: str) -> bool:
    return line.startswith("#!")

def has_encoding_cookie(line: str) -> bool:
    return ENCODING_COOKIE_RE.search(line) is not None

def should_keep_py_comment(comment_text: str, keep_keywords: Set[str]) -> bool:
    lower = comment_text.lower()
    return any(kw in lower for kw in keep_keywords)

def should_keep_sh_comment(comment_line: str, keep_keywords: Set[str]) -> bool:

    text_part = comment_line.lstrip()[1:].lstrip()
    lower = text_part.lower()
    return any(kw in lower for kw in keep_keywords)

def is_docstring(token: tokenize.TokenInfo, prev_tokens: List[tokenize.TokenInfo]) -> bool:
    token_str = token.string

    if len(token_str) >= 3:
        triple_double = '"' * 3
        triple_single = "'" * 3
        if not (token_str[:3] == triple_double or token_str[:3] == triple_single):
            return False
    else:
        return False

    if token_str.startswith('f"') or token_str.startswith("f'"):
        return False

    in_def_class_params = False
    for i, tok in enumerate(prev_tokens[-50:]):
        if tok.type in (tokenize.NL, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT):
            continue

        if tok.type == tokenize.NAME and tok.string in ('def', 'class', 'async'):
            in_def_class_params = True
            continue

        if tok.type == tokenize.OP and tok.string == '(':
            in_def_class_params = True
            continue

        if tok.type == tokenize.OP and tok.string == ')':
            continue

        if tok.type == tokenize.OP and tok.string == ':':
            in_def_class_params = False
            continue

        if tok.type == tokenize.OP and tok.string == '.':
            return False

        if tok.type == tokenize.OP and tok.string in ('=', ','):
            if not in_def_class_params:
                return False

            continue

        if tok.type == tokenize.OP:
            return False

    return True

def strip_python_comments(source: str, keep_keywords: Set[str]) -> str:
    lines = source.splitlines(keepends=True)
    preserved_prefix: List[str] = []
    remaining_start_index = 0

    if lines and has_shebang(lines[0]):
        preserved_prefix.append(lines[0])
        remaining_start_index = 1

    if remaining_start_index < len(lines) and has_encoding_cookie(lines[remaining_start_index]):
        preserved_prefix.append(lines[remaining_start_index])
        remaining_start_index += 1

    remaining = "".join(lines[remaining_start_index:])
    tokens: List[tokenize.TokenInfo] = []
    prev_tokens: List[tokenize.TokenInfo] = []
    try:
        tok_iter = tokenize.tokenize(io.BytesIO(remaining.encode("utf-8")).readline)
        for tok in tok_iter:
            if tok.type == tokenize.COMMENT:
                if should_keep_py_comment(tok.string, keep_keywords):
                    tokens.append(tok)
            elif tok.type == tokenize.STRING:

                if not is_docstring(tok, prev_tokens):
                    tokens.append(tok)
            else:
                tokens.append(tok)
            prev_tokens.append(tok)
    except tokenize.TokenError:
        return source

    try:
        processed = tokenize.untokenize(tokens)
        processed_text = processed.decode("utf-8") if isinstance(processed, bytes) else processed
    except Exception:
        return source

    processed_text = re.sub(r"\\\s*$", "", processed_text, flags=re.MULTILINE)
    processed_text = re.sub(r"\\\n", "\n", processed_text, flags=re.MULTILINE)

    processed_text = re.sub(r"[ \t]+$", "", processed_text, flags=re.MULTILINE)
    processed_text = re.sub(r"\n{3,}", "\n\n", processed_text)
    final_text = "".join(preserved_prefix) + processed_text
    if not final_text.endswith("\n"):
        final_text += "\n"
    return final_text

def strip_shell_comments(source: str, keep_keywords: Set[str]) -> str:
    lines = source.splitlines(keepends=True)
    if not lines:
        return ""

    new_lines: List[str] = []
    start_index = 0
    if has_shebang(lines[0]):
        new_lines.append(lines[0])
        start_index = 1

    for line in lines[start_index:]:
        stripped_line = line.lstrip()
        if stripped_line.startswith("#"):
            if should_keep_sh_comment(stripped_line, keep_keywords):
                new_lines.append(line)
        else:
            new_lines.append(line)

    result = "".join(new_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    if not result.endswith("\n"):
        result += "\n"
    return result

def write_if_changed(path: Path, new_content: str, dry_run: bool) -> bool:
    try:
        old_content = path.read_text(encoding="utf-8")
    except Exception:
        old_content = None
    if old_content == new_content:
        return False
    if dry_run:
        return True
    path.write_text(new_content, encoding="utf-8")
    return True

def run_command(cmd: List[str]) -> int:
    try:
        return subprocess.run(cmd, check=False).returncode
    except FileNotFoundError:
        print(f"[ERROR] Команда '{cmd[0]}' не найдена.", file=sys.stderr)
        return 127

def ensure_tool(cli_name: str, pip_name: Optional[str], allow_install: bool) -> bool:
    if shutil.which(cli_name):
        return True

    if not pip_name:
        print(f"[WARN] Инструмент '{cli_name}' не найден в PATH. Установите его вручную.")
        return False

    if not allow_install:
        print(f"[WARN] Инструмент '{cli_name}' не найден в PATH. Пропускаю установку.")
        return False

    print(f"[INFO] Устанавливаю '{pip_name}'...")
    code = run_command([sys.executable, "-m", "pip", "install", "-q", pip_name])
    if code != 0:
        print(f"[ERROR] Не удалось установить '{pip_name}'. Код: {code}", file=sys.stderr)
        return False
    return shutil.which(cli_name) is not None

def remove_multiline_docstrings_simple(source: str) -> str:
    lines = source.split('\n')
    result_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if i > 0:
            prev_line = lines[i-1].strip()

            if (prev_line.startswith('def ') or
                prev_line.startswith('async def ') or
                prev_line.startswith('class ')):

                line_stripped = line.strip()

                if line_stripped.startswith('"""') or line_stripped.startswith("'''"):

                    quote_char = line_stripped[0:3]

                    i += 1

                    close_idx = line_stripped.find(quote_char, 3)
                    if close_idx == -1:

                        while i < len(lines):
                            if quote_char in lines[i]:
                                i += 1
                                break
                            i += 1
                    continue

        result_lines.append(line)
        i += 1

    result_content = '\n'.join(result_lines)

    lines = result_content.split('\n')
    result_lines = []
    empty_count = 0
    for line in lines:
        if line.strip() == '':
            empty_count += 1
            if empty_count <= 2:
                result_lines.append('')
        else:
            empty_count = 0
            result_lines.append(line)

    result_content = '\n'.join(result_lines)
    if not result_content.endswith('\n') and source.endswith('\n'):
        result_content += '\n'

    return result_content

def apply_tooling(
    py_files: List[Path],
    sh_files: List[Path],
    skip_ruff: bool,
    skip_isort: bool,
    skip_black: bool,
    skip_shellcheck: bool,
    skip_shfmt: bool,
    allow_install: bool,
    line_length: int,
) -> None:
    """Применяет линтеры и форматтеры к файлам."""

    if py_files:
        py_targets = [str(p) for p in py_files]
        if not skip_ruff and ensure_tool("ruff", "ruff", allow_install):
            print("[INFO] Запуск: ruff (удаление неиспользуемых импортов/переменных)")
            run_command([sys.executable, "-m", "ruff", "check", "--select", "F", "--fix", *py_targets])

        if not skip_isort and ensure_tool("isort", "isort", allow_install):
            print("[INFO] Запуск: isort (сортировка импортов)")
            run_command([sys.executable, "-m", "isort", "--profile", "black", f"--line-length={line_length}", *py_targets])

        if not skip_black and ensure_tool("black", "black", allow_install):
            print("[INFO] Запуск: black (форматирование кода)")
            run_command([sys.executable, "-m", "black", f"--line-length={line_length}", *py_targets])

    if sh_files:
        sh_targets = [str(p) for p in sh_files]
        if not skip_shellcheck and ensure_tool("shellcheck", None, allow_install):
            print("[INFO] Запуск: shellcheck (анализ скриптов)")
            run_command(["shellcheck", *sh_targets])

        if not skip_shfmt and ensure_tool("shfmt", None, allow_install):
            print("[INFO] Запуск: shfmt (форматирование скриптов)")
            run_command(["shfmt", "-w", "-i", "4", *sh_targets])

def main(argv: Iterable[str] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Очистка Python (.py) и Shell (.sh) кода: удаление комментариев, "
            "линтеры и форматтеры. По умолчанию обрабатывает текущий каталог."
        )
    )

    parser.add_argument("paths", nargs="*", type=Path, help="Пути к файлам/папкам (по умолчанию: текущий каталог).")
    parser.add_argument("--dry-run", action="store_true", help="Показать изменения без записи на диск.")
    parser.add_argument("--only-comments", action="store_true", help="Только удалять комментарии, пропустить форматтеры.")
    parser.add_argument("--no-install", action="store_true", help="Не устанавливать автоматически отсутствующие инструменты.")
    parser.add_argument("--line-length", type=int, default=88, help="Длина строки для форматтеров (isort/black).")

    py_group = parser.add_argument_group("Python (.py) options")
    py_group.add_argument("--skip-ruff", action="store_true", help="Пропустить ruff.")
    py_group.add_argument("--skip-isort", action="store_true", help="Пропустить isort.")
    py_group.add_argument("--skip-black", action="store_true", help="Пропустить black.")
    py_group.add_argument("--keep-keywords", type=str, default=",".join(sorted(DEFAULT_KEEP_COMMENT_KEYWORDS)),
                          help="Ключевые слова для сохранения комментариев в Python (через запятую).")

    sh_group = parser.add_argument_group("Shell (.sh) options")
    sh_group.add_argument("--skip-shellcheck", action="store_true", help="Пропустить shellcheck.")
    sh_group.add_argument("--skip-shfmt", action="store_true", help="Пропустить shfmt.")
    sh_group.add_argument("--keep-sh-keywords", type=str, default=",".join(sorted(DEFAULT_KEEP_SHELL_COMMENT_KEYWORDS)),
                          help="Ключевые слова для сохранения комментариев в Shell (через запятую).")

    args = parser.parse_args(list(argv) if argv is not None else None)

    targets = [p.resolve() for p in args.paths] if args.paths else [Path.cwd()]

    if args.dry_run:
        print("[DRY-RUN] Режим пробного запуска: кэш удаляться не будет")
    else:
        print("[INFO] Удаляю кэш Python...")
        removed_count = remove_python_cache(targets)
        print(f"[INFO] Удалено элементов с кэшем Python: {removed_count}")

    source_files = discover_source_files(targets)
    py_files, sh_files = source_files["py"], source_files["sh"]

    if not py_files and not sh_files:
        print("[INFO] Не найдено Python или Shell файлов для обработки.")
        return 0

    py_keep_kw = {kw.strip().lower() for kw in args.keep_keywords.split(",") if kw.strip()}
    sh_keep_kw = {kw.strip().lower() for kw in args.keep_sh_keywords.split(",") if kw.strip()}

    changed_files: List[Path] = []

    for file_path in py_files:
        try:
            original = file_path.read_text(encoding="utf-8")
            cleaned = strip_python_comments(original, py_keep_kw)

            cleaned = remove_multiline_docstrings_simple(cleaned)

            if write_if_changed(file_path, cleaned, args.dry_run):
                changed_files.append(file_path)
        except Exception as e:
            print(f"[ERROR] Не удалось обработать файл {file_path}: {e}", file=sys.stderr)

    for file_path in sh_files:
        try:
            original = file_path.read_text(encoding="utf-8")
            cleaned = strip_shell_comments(original, sh_keep_kw)
            if write_if_changed(file_path, cleaned, args.dry_run):
                changed_files.append(file_path)
        except Exception as e:
            print(f"[ERROR] Не удалось обработать файл {file_path}: {e}", file=sys.stderr)

    if args.dry_run:
        print(f"[DRY-RUN] Будет изменено файлов после удаления комментариев: {len(changed_files)}")
        for f in changed_files:
            print(f"  - {f.relative_to(Path.cwd())}")
    else:
        print(f"[INFO] Изменено файлов (удаление комментариев): {len(changed_files)}")

    if not args.only_comments:
        apply_tooling(
            py_files=py_files,
            sh_files=sh_files,
            skip_ruff=args.skip_ruff,
            skip_isort=args.skip_isort,
            skip_black=args.skip_black,
            skip_shellcheck=args.skip_shellcheck,
            skip_shfmt=args.skip_shfmt,
            allow_install=not args.no_install,
            line_length=args.line_length,
        )

    print("[DONE] Завершено.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

