"""Sandboxed local filesystem tools."""

from mafuyu_ai.tools.safety import safe_path


def list_dir(path: str = ".") -> dict:
    """List files in any directory."""
    try:
        target = safe_path(path)
        if not target.exists():
            return {"error": f"Directory not found: {path}"}
        if not target.is_dir():
            return {"error": f"Not a directory: {path}"}

        items = []
        for item in target.iterdir():
            items.append(
                {
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                }
            )

        return {"path": str(target), "items": items}
    except Exception as e:
        return {"error": f"list_dir failed: {e}"}


def read_text(path: str) -> dict:
    """Read text file from any location."""
    try:
        target = safe_path(path)
        if not target.exists():
            return {"error": f"File not found: {path}"}
        if not target.is_file():
            return {"error": f"Not a file: {path}"}

        content = target.read_text(encoding="utf-8")
        return {"path": str(target), "content": content}
    except Exception as e:
        return {"error": f"read_text failed: {e}"}


def write_text(path: str, content: str) -> dict:
    """Write text file to any location."""
    try:
        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": str(target), "written": len(content), "success": True}
    except Exception as e:
        return {"error": f"write_text failed: {e}"}


def delete_file(path: str) -> dict:
    """Delete a file."""
    try:
        target = safe_path(path)
        if not target.exists():
            return {"error": f"File not found: {path}"}
        if target.is_dir():
            return {"error": f"Use delete_dir for directories: {path}"}
        target.unlink()
        return {"path": str(target), "deleted": True}
    except Exception as e:
        return {"error": f"delete_file failed: {e}"}


def delete_dir(path: str) -> dict:
    """Delete a directory and all contents."""
    import shutil

    try:
        target = safe_path(path)
        if not target.exists():
            return {"error": f"Directory not found: {path}"}
        if not target.is_dir():
            return {"error": f"Not a directory: {path}"}
        shutil.rmtree(target)
        return {"path": str(target), "deleted": True}
    except Exception as e:
        return {"error": f"delete_dir failed: {e}"}


def move_file(src: str, dst: str) -> dict:
    """Move/rename a file or directory."""
    import shutil

    try:
        src_path = safe_path(src)
        dst_path = safe_path(dst)
        if not src_path.exists():
            return {"error": f"Source not found: {src}"}
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        return {"src": str(src_path), "dst": str(dst_path), "moved": True}
    except Exception as e:
        return {"error": f"move_file failed: {e}"}


def copy_file(src: str, dst: str) -> dict:
    """Copy a file."""
    import shutil

    try:
        src_path = safe_path(src)
        dst_path = safe_path(dst)
        if not src_path.exists():
            return {"error": f"Source not found: {src}"}
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            shutil.copytree(str(src_path), str(dst_path))
        else:
            shutil.copy2(str(src_path), str(dst_path))
        return {"src": str(src_path), "dst": str(dst_path), "copied": True}
    except Exception as e:
        return {"error": f"copy_file failed: {e}"}


# ============ Fetch Tools ============
