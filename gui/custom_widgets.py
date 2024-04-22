from PyQt6.QtWidgets import QLineEdit, QPushButton
from PyQt6.QtCore import pyqtSignal

class CustomQLineEdit(QLineEdit):
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selectAll()

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
