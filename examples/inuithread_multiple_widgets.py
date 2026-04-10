import sys

from qtpy.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qonsole import PythonConsole


def greet():
    print("hello world")


if __name__ == "__main__":
    app = QApplication()

    # Create a main window with multiple widgets
    main_window = QWidget()
    main_window.setWindowTitle("Console Focus Test")
    main_window.resize(800, 600)

    layout = QVBoxLayout()

    # Add a label
    label = QLabel("Click text field below, then click console and try typing")
    layout.addWidget(label)

    # Add a text field you can click to take focus away from console
    text_field = QLineEdit()
    text_field.setPlaceholderText("Click here to take focus away from console")
    layout.addWidget(text_field)

    # Add a button
    button = QPushButton("I'm also clickable!")
    layout.addWidget(button)

    # Add the console
    console = PythonConsole(pygments_style="monokai")
    console.push_local_ns("greet", greet)
    layout.addWidget(console)

    main_window.setLayout(layout)
    main_window.show()

    console.eval_queued()

    sys.exit(app.exec_())
