"""
Copyright (C) 2024  Joonas Jormanainen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""""

import sys
from gui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("Amp Analyzer")
    window.show()
    window.on_load_clicked(ask_for_file_location=False)
    sys.exit(app.exec()) 

if __name__ == "__main__":
    main()
