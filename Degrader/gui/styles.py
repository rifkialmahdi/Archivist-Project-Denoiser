

DARK_THEME = """
    QMainWindow, QWidget {
        background-color: #1e1e1e;
        color: #ffffff;
        font-family: "Segoe UI", "Arial", sans-serif;
        font-size: 12px;
    }
    QWidget#SettingsPanel, QWidget#ControlsWidget { background-color: #252526; }
    QScrollArea { border: none; background-color: #252526; }

    /* Группы */
    QGroupBox {
        border: 1px solid #3e3e42;
        border-radius: 4px;
        margin-top: 20px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 5px;
        color: #4CAF50;
    }

    /* Чекбоксы */
    QCheckBox { spacing: 8px; }
    QCheckBox::indicator {
        width: 16px; height: 16px;
        background-color: #1e1e1e;
        border: 2px solid #555;
        border-radius: 3px;
    }
    QCheckBox::indicator:hover { border: 2px solid #888; }
    QCheckBox::indicator:checked {
        background-color: #4CAF50; border: 2px solid #4CAF50;
        image: none;
    }

    /* Слайдеры */
    QSlider::groove:horizontal {
        border: 1px solid #333; height: 4px;
        background: #1e1e1e; margin: 2px 0; border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: #4CAF50; border: 1px solid #4CAF50;
        width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
    }
    QSlider::handle:horizontal:hover { background: #66BB6A; }

    /* Спинбоксы */
    QSpinBox, QDoubleSpinBox {
        background-color: #1e1e1e; color: white;
        border: 1px solid #3e3e42; padding: 4px;
    }
    QSpinBox::up-button, QDoubleSpinBox::up-button {
        background-color: #333; width: 16px; border-left: 1px solid #454545;
    }
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        background-color: #333; width: 16px; border-left: 1px solid #454545;
    }

    /* Кнопки */
    QPushButton {
        background-color: #3e3e42; color: white; border: 1px solid #555;
        padding: 8px; border-radius: 4px; font-weight: bold;
    }
    QPushButton:hover { background-color: #505050; }
    QPushButton:pressed { background-color: #2ea043; }

    QPushButton#GenButton {
        background-color: #2ea043; font-size: 14px; border: none; padding: 15px;
    }
    QPushButton#GenButton:hover { background-color: #3fb950; }

    QProgressBar {
        border: 1px solid #454545; border-radius: 3px;
        text-align: center; background-color: #1e1e1e; color: white;
    }
    QProgressBar::chunk { background-color: #4CAF50; }

    QListWidget {
        background-color: #252526;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        color: #ddd;
    }
    /* Для диалога Batch */
    QDialog { background-color: #1e1e1e; }
"""

