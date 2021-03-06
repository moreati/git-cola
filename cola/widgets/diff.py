import os

from PyQt4 import QtGui
from PyQt4.QtCore import Qt, SIGNAL

import cola
from cola import qtutils
from cola import signals
from cola.qtutils import SLOT
from cola.widgets import defs
from cola.widgets.text import DiffTextEdit


class DiffEditor(DiffTextEdit):
    def __init__(self, parent):
        DiffTextEdit.__init__(self, parent)
        self.model = model = cola.model()
        self.mode = self.model.mode_none

        # Install diff shortcut keys for stage/unstage
        self.action_process_section = qtutils.add_action(self,
                'Process Section',
                self.apply_section, Qt.Key_H)
        self.action_process_selection = qtutils.add_action(self,
                'Process Selection',
                self.apply_selection, Qt.Key_S)

        # Context menu actions
        self.action_stage_selection = qtutils.add_action(self,
                self.tr('Stage &Selected Lines'),
                self.stage_selection)
        self.action_stage_selection.setIcon(qtutils.icon('add.svg'))
        self.action_stage_selection.setShortcut(Qt.Key_S)

        self.action_revert_selection = qtutils.add_action(self,
                self.tr('Revert Selected Lines...'),
                self.revert_selection)
        self.action_revert_selection.setIcon(qtutils.icon('undo.svg'))

        self.action_unstage_selection = qtutils.add_action(self,
                self.tr('Unstage &Selected Lines'),
                self.unstage_selection)
        self.action_unstage_selection.setIcon(qtutils.icon('remove.svg'))
        self.action_unstage_selection.setShortcut(Qt.Key_S)

        self.action_apply_selection = qtutils.add_action(self,
                self.tr('Apply Diff Selection to Work Tree'),
                self.stage_selection)
        self.action_apply_selection.setIcon(qtutils.apply_icon())

        model.add_observer(model.message_mode_about_to_change,
                           self._mode_about_to_change)
        model.add_observer(model.message_diff_text_changed, self.setPlainText)

        self.connect(self, SIGNAL('copyAvailable(bool)'),
                     self.enable_selection_actions)

    # Qt overrides
    def contextMenuEvent(self, event):
        """Create the context menu for the diff display."""
        menu = QtGui.QMenu(self)
        s = cola.selection()

        if self.model.stageable():
            if s.modified and s.modified[0] in cola.model().submodules:
                action = menu.addAction(qtutils.icon('add.svg'),
                                        self.tr('Stage'),
                                        SLOT(signals.stage, s.modified))
                action.setShortcut(defs.stage_shortcut)
                menu.addAction(qtutils.git_icon(),
                               self.tr('Launch git-cola'),
                               SLOT(signals.open_repo,
                                    os.path.abspath(s.modified[0])))
            elif s.modified:
                action = menu.addAction(qtutils.icon('add.svg'),
                                        self.tr('Stage Section'),
                                        self.stage_section)
                action.setShortcut(Qt.Key_H)
                menu.addAction(self.action_stage_selection)
                menu.addSeparator()
                menu.addAction(qtutils.icon('undo.svg'),
                               self.tr('Revert Section...'),
                               self.revert_section)
                menu.addAction(self.action_revert_selection)

        if self.model.unstageable():
            if s.staged and s.staged[0] in cola.model().submodules:
                action = menu.addAction(qtutils.icon('remove.svg'),
                                        self.tr('Unstage'),
                                        SLOT(signals.unstage, s.staged))
                action.setShortcut(defs.stage_shortcut)
                menu.addAction(qtutils.git_icon(),
                               self.tr('Launch git-cola'),
                               SLOT(signals.open_repo,
                                    os.path.abspath(s.staged[0])))
            elif s.staged:
                action = menu.addAction(qtutils.icon('remove.svg'),
                                        self.tr('Unstage Section'),
                                        self.unstage_section)
                action.setShortcut(Qt.Key_H)
                menu.addAction(self.action_unstage_selection)

        menu.addSeparator()
        action = menu.addAction(qtutils.icon('edit-copy.svg'),
                                'Copy', self.copy)
        action.setShortcut(QtGui.QKeySequence.Copy)

        action = menu.addAction(qtutils.icon('edit-select-all.svg'),
                                'Select All', self.selectAll)
        action.setShortcut(QtGui.QKeySequence.SelectAll)
        menu.exec_(self.mapToGlobal(event.pos()))

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            # Intercept the Control modifier to not resize the text
            # when doing control+mousewheel
            event.accept()
            event = QtGui.QWheelEvent(event.pos(), event.delta(),
                                      Qt.NoButton,
                                      Qt.NoModifier,
                                      event.orientation())
        return DiffTextEdit.wheelEvent(self, event)

    def _mode_about_to_change(self, mode):
        self.mode = mode

    def setPlainText(self, text):
        """setPlainText(str) while retaining scrollbar positions"""
        highlight = (self.mode != self.model.mode_none and
                     self.mode != self.model.mode_untracked)
        self.highlighter.set_enabled(highlight)
        scrollbar = self.verticalScrollBar()
        if scrollbar:
            scrollvalue = scrollbar.value()
        if text is not None:
            DiffTextEdit.setPlainText(self, text)
            if scrollbar:
                scrollbar.setValue(scrollvalue)

    def offset_and_selection(self):
        cursor = self.textCursor()
        offset = cursor.position()
        selection = unicode(cursor.selection().toPlainText())
        return offset, selection

    # Mutators
    def enable_selection_actions(self, enabled):
        self.action_apply_selection.setEnabled(enabled)
        self.action_revert_selection.setEnabled(enabled)
        self.action_unstage_selection.setEnabled(enabled)
        self.action_stage_selection.setEnabled(enabled)

    def apply_section(self):
        s = cola.single_selection()
        if self.model.stageable() and s.modified:
            self.stage_section()
        elif self.model.unstageable():
            self.unstage_section()

    def apply_selection(self):
        s = cola.single_selection()
        if self.model.stageable() and s.modified:
            self.stage_selection()
        elif self.model.unstageable():
            self.unstage_selection()

    def stage_section(self):
        """Stage a specific section."""
        self.process_diff_selection(staged=False)

    def stage_selection(self):
        """Stage selected lines."""
        self.process_diff_selection(staged=False, selected=True)

    def unstage_section(self, cached=True):
        """Unstage a section."""
        self.process_diff_selection(staged=True)

    def unstage_selection(self):
        """Unstage selected lines."""
        self.process_diff_selection(staged=True, selected=True)

    def revert_section(self):
        """Destructively remove a section from a worktree file."""
        if not qtutils.confirm('Revert Section?',
                               'This operation drops uncommitted changes.\n'
                               'These changes cannot be recovered.',
                               'Revert the uncommitted changes?',
                               'Revert Section',
                               default=True,
                               icon=qtutils.icon('undo.svg')):
            return
        self.process_diff_selection(staged=False, apply_to_worktree=True,
                                    reverse=True)

    def revert_selection(self):
        """Destructively check out content for the selected file from $head."""
        if not qtutils.confirm('Revert Selected Lines?',
                               'This operation drops uncommitted changes.\n'
                               'These changes cannot be recovered.',
                               'Revert the uncommitted changes?',
                               'Revert Selected Lines',
                               default=True,
                               icon=qtutils.icon('undo.svg')):
            return
        self.process_diff_selection(staged=False, apply_to_worktree=True,
                                    reverse=True, selected=True)

    def process_diff_selection(self, selected=False,
                               staged=True, apply_to_worktree=False,
                               reverse=False):
        """Implement un/staging of selected lines or sections."""
        offset, selection = self.offset_and_selection()
        cola.notifier().broadcast(signals.apply_diff_selection,
                                  staged,
                                  selected,
                                  offset,
                                  selection,
                                  apply_to_worktree)
