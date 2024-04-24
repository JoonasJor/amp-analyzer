from PyQt6.QtWidgets import QLineEdit, QPushButton, QScrollArea
from PyQt6.QtCore import pyqtSignal, Qt

class CustomQLineEdit(QLineEdit):
    # Selects all text on mouse click
    # Allows moving and copying between line edits with arrow keys + ctrl
    
    custom_line_edit_sets = {}
    main_window = None

    def __init__(self, set_index, text, parent=None):
        super().__init__(text, parent)
        self.main_window = parent
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.set_index = set_index
        if set_index not in self.custom_line_edit_sets:
            self.custom_line_edit_sets[set_index] = []
        
        self.custom_line_edit_sets[set_index].append(self)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selectAll()

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        if event.key() == Qt.Key.Key_Up:
            if modifiers == Qt.KeyboardModifier.ControlModifier:
                # Ctrl + Up Arrow
                self.focusLineEdit(-1, True)
            elif modifiers == Qt.KeyboardModifier.NoModifier:
                # Up Arrow
                self.focusLineEdit(-1, False)
        elif event.key() == Qt.Key.Key_Down:
            if modifiers == Qt.KeyboardModifier.ControlModifier:
                # Ctrl + Down Arrow
                self.focusLineEdit(1, True)
            elif modifiers == Qt.KeyboardModifier.NoModifier:
                # Down Arrow
                self.focusLineEdit(1, False)
        else:
            super().keyPressEvent(event)


    def focusLineEdit(self, step: int, copy_text: bool):
        current_set = self.custom_line_edit_sets[self.set_index]
        current_index = current_set.index(self)
        
        next_index = current_index + step
        
        # Check if next_index is out of bounds
        if next_index >= len(current_set) or next_index < 0:
            return
            
        while not current_set[next_index].isEnabled():
            next_index += step
            
            # Check if next_index is out of bounds
            if next_index >= len(current_set) or next_index < 0:
                return
        
        next_line_edit: CustomQLineEdit = current_set[next_index]
        if copy_text:
            next_line_edit.setText(self.text())
        next_line_edit.setFocus()
        next_line_edit.selectAll()
        
        scroll_area: QScrollArea = self.main_window.scrollArea_datasets
        scroll_area.ensureWidgetVisible(next_line_edit)

class EditableButton(QPushButton):
    btnTextEditingFinished = pyqtSignal(str)

    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setCheckable(False)
        self.line_edit = None
        self.currently_editing = False
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        # Start editing on double click
        if obj == self and event.type() == event.Type.MouseButtonDblClick:
            self.start_editing()
            return True
        # Finish editing if line edit loses focus without the text changing
        elif obj == self.line_edit and event.type() == event.Type.FocusOut:
            self.finish_editing()
            return True
        return super().eventFilter(obj, event)

    def start_editing(self):      
        if self.currently_editing:
            return
        
        self.currently_editing = True
        self.setStyleSheet("")
        self.old_text = self.text()

        # Create line edit on top of the button
        self.line_edit = QLineEdit(self.old_text, self)
        self.line_edit.selectAll()
        self.line_edit.setFocus()
        self.line_edit.editingFinished.connect(self.finish_editing)
        self.line_edit.setGeometry(self.rect())
        self.line_edit.show()
        self.line_edit.installEventFilter(self)

    def finish_editing(self):
        if not self.currently_editing:
            return
        
        self.currently_editing = False
        # Set button text to edited text
        new_text = self.line_edit.text()
        self.setText(new_text)

        self.btnTextEditingFinished.emit(new_text)

        # Delete line edit and reset stylesheet on button
        self.line_edit.deleteLater()
        self.setStyleSheet("background-color: rgba(128, 128, 255, 0.3)")
