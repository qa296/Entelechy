"""File tools - read, write, edit files with path safety."""

import aiofiles
from pathlib import Path


from utils.path_utils import safe_path


async def run_read(
    path: str, workdir: Path | None = None, limit: int | None = None
) -> str:
    """Read a file.

    Args:
        path: Relative or absolute file path.
        workdir: Base directory for path safety.
        limit: Maximum number of lines to read.

    Returns:
        File content or error message.
    """
    try:
        if workdir:
            file_path = safe_path(workdir, path)
        else:
            file_path = Path(path).resolve()

        if not file_path.exists():
            return f"Error: File not found: {path}"

        async with aiofiles.open(file_path, "r", encoding="utf-8", errors="replace") as f:
            if limit:
                lines = []
                for i, line in enumerate(await f.readlines()):
                    if i >= limit:
                        break
                    lines.append(line)
                content = "".join(lines)
            else:
                content = await f.read()

        # Truncate very long files
        if len(content) > 100000:
            content = content[:100000] + "\n\n... (file truncated at 100000 chars)"

        return content
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


async def run_write(path: str, content: str, workdir: Path | None = None) -> str:
    """Write content to a file, creating parent directories as needed.

    Args:
        path: Relative or absolute file path.
        content: Content to write.
        workdir: Base directory for path safety.

    Returns:
        Success message or error.
    """
    try:
        if workdir:
            file_path = safe_path(workdir, path)
        else:
            file_path = Path(path).resolve()

        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

        return f"File written: {file_path} ({len(content)} chars)"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error writing file: {e}"


async def run_edit(
    path: str, old_text: str, new_text: str, workdir: Path | None = None
) -> str:
    """Replace exact text in a file.

    Args:
        path: Relative or absolute file path.
        old_text: Exact text to find.
        new_text: Text to replace with.
        workdir: Base directory for path safety.

    Returns:
        Success message or error.
    """
    try:
        if workdir:
            file_path = safe_path(workdir, path)
        else:
            file_path = Path(path).resolve()

        if not file_path.exists():
            return f"Error: File not found: {path}"

        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        if old_text not in content:
            return f"Error: old_text not found in {path}"

        count = content.count(old_text)
        new_content = content.replace(old_text, new_text, 1)

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(new_content)

        msg = f"File edited: {file_path}"
        if count > 1:
            msg += f" (replaced first of {count} occurrences)"
        return msg
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error editing file: {e}"
