
from __future__ import annotations

from copy import deepcopy
from PySide6.QtGui import QUndoCommand


class AddSymbolCommand(QUndoCommand):
    def __init__(self, window, placement, text: str = "Placér symbol"):
        super().__init__(text)
        self.window = window
        self.placement = placement

    def redo(self) -> None:
        self.window._add_placement(self.placement)

    def undo(self) -> None:
        self.window._remove_placement(self.placement.uid)


class DeleteSymbolCommand(QUndoCommand):
    def __init__(self, window, placement, index: int, text: str = "Slet symbol"):
        super().__init__(text)
        self.window = window
        self.placement = placement
        self.index = index
        # Deletion must not leave ghost a/b/c relations, spot parents or cable UIDs.
        # Keep a full reference snapshot so Undo restores them exactly.
        self.reference_state = window._symbol_reference_snapshot()

    def redo(self) -> None:
        self.window._remove_placement(self.placement.uid)
        self.window._cleanup_after_symbol_removed(self.placement.uid)

    def undo(self) -> None:
        self.window._add_placement(self.placement, self.index)
        self.window._restore_symbol_reference_snapshot(self.reference_state)


class MoveSymbolCommand(QUndoCommand):
    def __init__(self, window, uid: str, old_pose, new_pose, already_applied: bool = True):
        super().__init__("Flyt symbol")
        self.window = window
        self.uid = uid
        self.old_pose = tuple(old_pose)
        self.new_pose = tuple(new_pose)
        self._skip_first_redo = bool(already_applied)

    def redo(self) -> None:
        if self._skip_first_redo:
            self._skip_first_redo = False
            return
        self.window._set_symbol_pose(self.uid, self.new_pose)

    def undo(self) -> None:
        self.window._set_symbol_pose(self.uid, self.old_pose)


class EditSymbolCommand(QUndoCommand):
    def __init__(self, window, uid: str, before: dict, after: dict, text: str = "Redigér symbol", already_applied: bool = False):
        super().__init__(text)
        self.window = window
        self.uid = uid
        self.before = deepcopy(before)
        self.after = deepcopy(after)
        self._skip_first_redo = bool(already_applied)

    def redo(self) -> None:
        if self._skip_first_redo:
            self._skip_first_redo = False
            return
        self.window._apply_symbol_state(self.uid, self.after)

    def undo(self) -> None:
        self.window._apply_symbol_state(self.uid, self.before)


class AddCableCommand(QUndoCommand):
    def __init__(self, window, cable, text: str = "Tegn kabel"):
        super().__init__(text)
        self.window = window
        self.cable = cable

    def redo(self) -> None:
        self.window._add_cable(self.cable)

    def undo(self) -> None:
        self.window._remove_cable(self.cable)


class AddCableBatchCommand(QUndoCommand):
    """Add/undo one user-drawn cable string as multiple physical cables."""
    def __init__(self, window, cables, text: str = "Tegn kabelstreng"):
        super().__init__(text)
        self.window = window
        self.cables = list(cables or [])

    def redo(self) -> None:
        for cable in self.cables:
            self.window._add_cable(cable)

    def undo(self) -> None:
        for cable in reversed(self.cables):
            self.window._remove_cable(cable)


class CableArticleBindingsCommand(QUndoCommand):
    def __init__(self, window, before: dict, after: dict, text: str = "Kabelartikler"):
        super().__init__(text)
        self.window=window
        self.before=deepcopy(before)
        self.after=deepcopy(after)

    def _apply(self, value) -> None:
        import core_logic as core
        self.window.project.raw["cable_instance_articles"]=core.normalize_cable_article_bindings(value)
        self.window.project.dirty=True
        self.window._update_title()
        if hasattr(self.window,"_refresh_cable_article_ui"):
            self.window._refresh_cable_article_ui()

    def redo(self) -> None:
        self._apply(self.after)

    def undo(self) -> None:
        self._apply(self.before)


class AssociationCommand(QUndoCommand):
    def __init__(self, window, before: dict, after: dict, text: str = "Tilhørsforhold"):
        super().__init__(text)
        self.window = window
        self.before = deepcopy(before)
        self.after = deepcopy(after)

    def redo(self) -> None:
        self.window._apply_association_state(self.after)

    def undo(self) -> None:
        self.window._apply_association_state(self.before)


class AddTextCommand(QUndoCommand):
    def __init__(self, window, item, text: str = "Tilføj tekst"):
        super().__init__(text)
        self.window = window
        self.item = item

    def redo(self) -> None:
        self.window._add_text(self.item)

    def undo(self) -> None:
        self.window._remove_text(self.item.uid)


class DeleteTextCommand(QUndoCommand):
    def __init__(self, window, item, index: int, text: str = "Slet tekst"):
        super().__init__(text)
        self.window = window
        self.item = item
        self.index = index

    def redo(self) -> None:
        self.window._remove_text(self.item.uid)

    def undo(self) -> None:
        self.window._add_text(self.item, self.index)


class EditTextCommand(QUndoCommand):
    def __init__(self, window, uid: str, before: dict, after: dict, text: str = "Redigér tekst"):
        super().__init__(text)
        self.window = window
        self.uid = uid
        self.before = deepcopy(before)
        self.after = deepcopy(after)

    def redo(self) -> None:
        self.window._apply_text_state(self.uid, self.after)

    def undo(self) -> None:
        self.window._apply_text_state(self.uid, self.before)


class SpotParentCommand(QUndoCommand):
    def __init__(self, window, before: dict, after: dict, text: str = "Tilknyt spots"):
        super().__init__(text)
        self.window = window
        self.before = deepcopy(before)
        self.after = deepcopy(after)

    def redo(self) -> None:
        self.window._apply_spot_parent_state(self.after)

    def undo(self) -> None:
        self.window._apply_spot_parent_state(self.before)


class EditCableCommand(QUndoCommand):
    def __init__(self, window, cable, before: dict, after: dict, text: str = "Redigér kabel", already_applied: bool = False):
        super().__init__(text)
        self.window = window
        self.cable = cable
        self.before = deepcopy(before)
        self.after = deepcopy(after)
        self._skip_first_redo = bool(already_applied)

    def redo(self) -> None:
        if self._skip_first_redo:
            self._skip_first_redo = False
            return
        self.window._apply_cable_state(self.cable, self.after)

    def undo(self) -> None:
        self.window._apply_cable_state(self.cable, self.before)


class DeleteCableCommand(QUndoCommand):
    def __init__(self, window, cable, index: int, text: str = "Slet kabel"):
        super().__init__(text)
        self.window = window
        self.cable = cable
        self.index = index
        import core_logic as core
        bindings=core.normalize_cable_article_bindings(window.project.raw.get("cable_instance_articles",{}))
        self.article_no=bindings.get(str(getattr(cable,"uid","") or ""),"")

    def _set_article(self, article_no: str) -> None:
        import core_logic as core
        bindings=core.normalize_cable_article_bindings(self.window.project.raw.get("cable_instance_articles",{}))
        uid=str(getattr(self.cable,"uid","") or "")
        if article_no:bindings[uid]=article_no
        else:bindings.pop(uid,None)
        self.window.project.raw["cable_instance_articles"]=bindings
        if hasattr(self.window,"_refresh_cable_article_ui"):self.window._refresh_cable_article_ui()

    def redo(self) -> None:
        self.window._remove_cable(self.cable)
        self._set_article("")

    def undo(self) -> None:
        self.window._add_cable(self.cable, self.index)
        self._set_article(self.article_no)
