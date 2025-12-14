
import sys
from PyQt6.QtWidgets import QApplication
from gui.window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())
