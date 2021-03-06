"""Provides the StashView dialog."""

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import Qt
from PyQt4.QtCore import SIGNAL

from cola import qt
from cola import qtutils
from cola import utils
from cola.stash.model import save_stash, apply_stash, drop_stash, rescan
from cola.widgets import defs
from cola.widgets.text import DiffTextEdit
from cola.widgets.standard import Dialog


class StashView(Dialog):
    def __init__(self, model, parent=None):
        Dialog.__init__(self, parent=parent)
        self.setAttribute(Qt.WA_MacMetalStyle)
        self.model = model
        self.stashes = []
        self.revids = []
        self.names = []

        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setWindowTitle(self.tr('Stash'))
        if parent:
            self.resize(parent.width(), 420)
        else:
            self.resize(700, 420)

        self.stash_list = QtGui.QListWidget(self)
        self.stash_text = DiffTextEdit(self)

        self.button_apply =\
            self.toolbutton(self.tr('Apply'),
                            self.tr('Apply the selected stash'),
                            qtutils.apply_icon())
        self.button_save =\
            self.toolbutton(self.tr('Save'),
                            self.tr('Save modified state to new stash'),
                            qtutils.save_icon())
        self.button_drop = \
            self.toolbutton(self.tr('Drop'),
                            self.tr('Drop the selected stash'),
                            qtutils.discard_icon())
        self.button_close = \
            self.pushbutton(self.tr('Close'),
                            self.tr('Close'), qtutils.close_icon())

        self.keep_index = QtGui.QCheckBox(self)
        self.keep_index.setText(self.tr('Keep Index'))
        self.keep_index.setChecked(True)

        # Arrange layouts
        self.main_layt = QtGui.QVBoxLayout()
        self.main_layt.setMargin(defs.margin)
        self.main_layt.setSpacing(defs.spacing)

        self.btn_layt = QtGui.QHBoxLayout()
        self.btn_layt.setMargin(0)
        self.btn_layt.setSpacing(defs.spacing)

        self.splitter = QtGui.QSplitter()
        self.splitter.setHandleWidth(defs.handle_width)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(True)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.insertWidget(0, self.stash_list)
        self.splitter.insertWidget(1, self.stash_text)

        self.btn_layt.addWidget(self.button_save)
        self.btn_layt.addWidget(self.button_apply)
        self.btn_layt.addWidget(self.button_drop)
        self.btn_layt.addWidget(self.keep_index)
        self.btn_layt.addStretch()
        self.btn_layt.addWidget(self.button_close)

        self.main_layt.addWidget(self.splitter)
        self.main_layt.addLayout(self.btn_layt)
        self.setLayout(self.main_layt)

        self.splitter.setSizes([self.width()/3, self.width()*2/3])

        self.update_from_model()
        self.update_actions()

        self.setTabOrder(self.button_save, self.button_apply)
        self.setTabOrder(self.button_apply, self.button_drop)
        self.setTabOrder(self.button_drop, self.keep_index)
        self.setTabOrder(self.keep_index, self.button_close)

        self.connect(self.stash_list, SIGNAL('itemSelectionChanged()'),
                     self.item_selected)

        qtutils.connect_button(self.button_apply, self.stash_apply)
        qtutils.connect_button(self.button_save, self.stash_save)
        qtutils.connect_button(self.button_drop, self.stash_drop)
        qtutils.connect_button(self.button_close, self.close)

    def close(self):
        self.accept()
        self.emit(SIGNAL(rescan))

    def toolbutton(self, text, tooltip, icon):
        return qt.create_toolbutton(text=text, tooltip=tooltip, icon=icon)

    def pushbutton(self, text, tooltip, icon):
        btn = QtGui.QPushButton(self)
        btn.setText(self.tr(text))
        btn.setToolTip(self.tr(tooltip))
        btn.setIcon(icon)
        return btn

    def selected_stash(self):
        """Returns the stash name of the currently selected stash
        """
        list_widget = self.stash_list
        stash_list = self.revids
        return qtutils.selected_item(list_widget, stash_list)

    def selected_name(self):
        list_widget = self.stash_list
        stash_list = self.names
        return qtutils.selected_item(list_widget, stash_list)

    def item_selected(self):
        """Shows the current stash in the main view."""
        self.update_actions()
        selection = self.selected_stash()
        if not selection:
            return
        diff_text = self.model.stash_diff(selection)
        self.stash_text.setPlainText(diff_text)

    def update_actions(self):
        has_changes = self.model.has_stashable_changes()
        has_stash = bool(self.selected_stash())
        self.button_save.setEnabled(has_changes)
        self.button_apply.setEnabled(has_stash)
        self.button_drop.setEnabled(has_stash)

    def update_from_model(self):
        """Initiates git queries on the model and updates the view
        """
        stashes, revids, names = self.model.stash_info()
        self.stashes = stashes
        self.revids = revids
        self.names = names

        self.stash_list.clear()
        self.stash_list.addItems(self.stashes)

    def stash_apply(self):
        """Applies the currently selected stash
        """
        selection = self.selected_stash()
        if not selection:
            return
        index = self.keep_index.isChecked()
        self.emit(SIGNAL(apply_stash), selection, index)
        self.accept()
        self.emit(SIGNAL(rescan))

    def stash_save(self):
        """Saves the worktree in a stash

        This prompts the user for a stash name and creates
        a git stash named accordingly.

        """
        stash_name, ok = qtutils.prompt('Save Stash',
                                        'Enter a name for the stash')
        if not ok or not stash_name:
            return
        # Sanitize the stash name
        stash_name = utils.sanitize(stash_name)
        if stash_name in self.names:
            qtutils.critical('Oops!',
                             'A stash named "%s" already exists' % stash_name)
            return

        keep_index = self.keep_index.isChecked()
        self.emit(SIGNAL(save_stash), stash_name, keep_index)
        self.accept()
        self.emit(SIGNAL(rescan))

    def stash_drop(self):
        """Drops the currently selected stash
        """
        selection = self.selected_stash()
        name = self.selected_name()
        if not selection:
            return
        if not qtutils.confirm('Drop Stash?',
                               'Recovering a dropped stash is not possible.',
                               'Drop the "%s" stash?' % name,
                               'Drop Stash',
                               default=True,
                               icon=qtutils.discard_icon()):
            return
        self.emit(SIGNAL(drop_stash), selection)
        self.update_from_model()
        self.stash_text.setPlainText('')
