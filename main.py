"""Точка входа приложения MemoCards."""
import sys

from PyQt6.QtWidgets import QApplication

from database import Database
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    db = Database("memocards.db")
    window = MainWindow(db)
    window.show()
    code = app.exec()
    db.close()
    sys.exit(code)


if __name__ == "__main__":
    main()
