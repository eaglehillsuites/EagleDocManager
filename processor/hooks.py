"""
Processing Hooks - Extensible hook system for post-processing actions.
Hooks can be registered to run after rename, move, or batch completion.
"""

from typing import Callable, Optional


class ProcessingHooks:
    """
    Central hook registry. Add hooks to extend functionality without 
    modifying the core engine.
    
    Available hooks:
    - after_rename(file_info: dict)
    - after_move(file_info: dict)
    - after_batch_complete(batch_results: list)
    - on_error(error_info: dict)
    - on_out_inspection(unit: str, file_path: str)
    """

    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {
            "after_rename": [],
            "after_move": [],
            "after_batch_complete": [],
            "on_error": [],
            "on_out_inspection": [],
        }

    def register(self, hook_name: str, fn: Callable):
        """Register a function to a named hook."""
        if hook_name in self._hooks:
            self._hooks[hook_name].append(fn)

    def unregister(self, hook_name: str, fn: Callable):
        """Remove a function from a named hook."""
        if hook_name in self._hooks:
            try:
                self._hooks[hook_name].remove(fn)
            except ValueError:
                pass

    def fire(self, hook_name: str, *args, **kwargs):
        """Fire all registered functions for a hook."""
        for fn in self._hooks.get(hook_name, []):
            try:
                fn(*args, **kwargs)
            except Exception as e:
                print(f"[Hook Error] {hook_name}: {e}")

    def clear(self, hook_name: Optional[str] = None):
        """Clear all hooks, or just one hook by name."""
        if hook_name:
            self._hooks[hook_name] = []
        else:
            for k in self._hooks:
                self._hooks[k] = []


# Global instance
hooks = ProcessingHooks()
