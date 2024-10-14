from PyQt5 import QtWidgets, QtGui, QtCore
import sys, threading, os, string, ctypes

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_available_drives():
    drives = []
    for drive in string.ascii_uppercase:
        drive_path = f"{drive}:\\"
        if os.path.exists(drive_path):
            drives.append(drive_path)
    return drives

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class DirectoryScanner(QtCore.QObject):
    update_result = QtCore.pyqtSignal(tuple)
    scanning_finished = QtCore.pyqtSignal()

    def __init__(self, start_path, min_size=1*1024**3):
        super().__init__()
        self.start_path = start_path
        self.min_size = min_size

    def start_scanning(self):
        threading.Thread(target=self.scan_directory, args=(self.start_path,), daemon=True).start()

    def scan_directory(self, directory):
        total_size = 0
        try:
            entries = list(os.scandir(directory))
        except PermissionError:
            print(f"Permission denied: {directory}")
            return 0
        except Exception as e:
            print(f"Error accessing {directory}: {e}")
            return 0

        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                elif entry.is_file():
                    try:
                        size = entry.stat(follow_symlinks=False).st_size
                        total_size += size
                    except PermissionError:
                        print(f"Permission denied: {entry.path}")
                    except Exception as e:
                        print(f"Error accessing file {entry.path}: {e}")
                elif entry.is_dir():
                    size = self.scan_directory(entry.path)
                    total_size += size
            except Exception as e:
                print(f"Error processing {entry.path}: {e}")

        if total_size >= self.min_size:
            self.update_result.emit((directory, total_size))

        if directory == self.start_path:
            self.scanning_finished.emit()

        return total_size

class RoundedWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.resize(800, 600)
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        self.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))
        self.logo = QtWidgets.QLabel(self)
        self.logo.setPixmap(QtGui.QPixmap(resource_path("logo.png")))
        self.logo.setScaledContents(True)
        self.closeButton = QtWidgets.QPushButton("✕", self)
        self.closeButton.clicked.connect(self.close)
        self.driveSelector = QtWidgets.QComboBox(self)
        self.driveSelector.addItems(get_available_drives())
        self.driveSelector.currentIndexChanged.connect(self.start_scanning)
        self.scrollArea = QtWidgets.QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollContent = QtWidgets.QWidget()
        self.scrollArea.setWidget(self.scrollContent)
        self.scrollLayout = QtWidgets.QVBoxLayout(self.scrollContent)
        self.scrollContent.setStyleSheet("background-color: lightgrey;")
        self.old_position = None
        self.resizing = False
        self.resize_edge = None
        self.setMouseTracking(True)
        self.update_widget_positions()
        self.results = []
        self.start_scanning()

    def update_widget_positions(self):
        window_width = self.width()
        window_height = self.height()

        logo_width = int(window_width * 0.60)
        logo_height = int(window_height * 0.25)
        self.logo.setGeometry(
            (window_width - logo_width) // 2,
            int(window_height * 0.05),
            logo_width,
            logo_height
        )

        button_size = int(window_height * 0.1)
        button_margin = int(window_height * 0.04)
        self.closeButton.setGeometry(
            window_width - button_size - button_margin,
            button_margin,
            button_size,
            button_size
        )

        drive_selector_width = int(window_width * 0.5)
        drive_selector_height = int(window_height * 0.1)
        self.driveSelector.setGeometry(
            (window_width - drive_selector_width) // 2,
            window_height - drive_selector_height - int(window_height * 0.05),
            drive_selector_width,
            drive_selector_height
        )

        scroll_x = int(window_width * 0.05)
        scroll_y = self.logo.y() + self.logo.height() + int(window_height * 0.02)
        scroll_width = window_width - 2 * scroll_x
        scroll_height = self.driveSelector.y() - scroll_y - int(window_height * 0.02)
        self.scrollArea.setGeometry(
            scroll_x,
            scroll_y,
            scroll_width,
            scroll_height
        )

        font_size = max(8, int(window_height * 0.04))
        self.closeButton.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #00abdf;
                border-radius: {button_size // 2}px;
                color: white;
                font-weight: bold;
                font-size: {font_size}px;
            }}
            QPushButton:hover {{
                background-color: #33c4ff;
            }}
            """
        )

        self.driveSelector.setStyleSheet(
            f"""
            QComboBox {{
                background-color: #00abdf;
                color: white;
                border-radius: {drive_selector_height // 2}px;
                font-weight: bold;
                padding: 5px 20px;
                font-size: {font_size}px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: white;
                selection-background-color: #00abdf;
                selection-color: white;
            }}
            """
        )

    def display_scanning_message(self):
        for i in reversed(range(self.scrollLayout.count())):
            widget_to_remove = self.scrollLayout.itemAt(i).widget()
            self.scrollLayout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)
        label = QtWidgets.QLabel("Scanning...")
        self.scrollLayout.addWidget(label)

    def start_scanning(self):
        selected_drive = self.driveSelector.currentText()
        self.display_scanning_message()
        self.results = []
        self.scanner = DirectoryScanner(selected_drive)
        self.scanner.update_result.connect(self.add_result)
        self.scanner.scanning_finished.connect(self.scanning_finished)
        self.scanner.start_scanning()

    def add_result(self, result):
        dir_path, size = result
        self.results.append((dir_path, size))
        self.results.sort(key=lambda x: x[1], reverse=True)
        self.display_results(self.results)

    def display_results(self, results):
        for i in reversed(range(self.scrollLayout.count())):
            widget_to_remove = self.scrollLayout.itemAt(i).widget()
            self.scrollLayout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)

        for dir_path, size in results:
            size_gb = size / (1024**3)
            label = QtWidgets.QLabel(f"{dir_path} - {size_gb:.2f} GB")
            self.scrollLayout.addWidget(label)

    def scanning_finished(self):
        label = QtWidgets.QLabel("Scanning complete.")
        self.scrollLayout.addWidget(label)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        gradient = QtGui.QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QtGui.QColor(58, 63, 75))
        gradient.setColorAt(1, QtGui.QColor(88, 93, 105))
        painter.setBrush(QtGui.QBrush(gradient))
        painter.setPen(QtCore.Qt.NoPen)
        corner_radius = max(20, int(min(self.width(), self.height()) * 0.05))
        painter.drawRoundedRect(rect, corner_radius, corner_radius)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            margin = 5
            pos = event.pos()
            rect = self.rect()
            self.resizing = False
            self.resize_edge = None
            if pos.x() < margin and pos.y() < margin:
                self.resizing = True
                self.resize_edge = 'top-left'
            elif pos.x() > rect.width() - margin and pos.y() < margin:
                self.resizing = True
                self.resize_edge = 'top-right'
            elif pos.x() < margin and pos.y() > rect.height() - margin:
                self.resizing = True
                self.resize_edge = 'bottom-left'
            elif pos.x() > rect.width() - margin and pos.y() > rect.height() - margin:
                self.resizing = True
                self.resize_edge = 'bottom-right'
            elif pos.x() < margin:
                self.resizing = True
                self.resize_edge = 'left'
            elif pos.x() > rect.width() - margin:
                self.resizing = True
                self.resize_edge = 'right'
            elif pos.y() < margin:
                self.resizing = True
                self.resize_edge = 'top'
            elif pos.y() > rect.height() - margin:
                self.resizing = True
                self.resize_edge = 'bottom'
            else:
                self.old_position = event.globalPos()

    def mouseMoveEvent(self, event):
        screen_rect = QtWidgets.QApplication.primaryScreen().geometry()
        min_width = 200
        min_height = 150

        if self.resizing:
            pos = event.globalPos()
            geo = self.geometry()

            if self.resize_edge == 'top-left':
                new_x = pos.x()
                new_y = pos.y()
                new_w = geo.x() + geo.width() - new_x
                new_h = geo.y() + geo.height() - new_y

                if new_w < min_width:
                    new_w = min_width
                    new_x = geo.x() + geo.width() - new_w
                if new_h < min_height:
                    new_h = min_height
                    new_y = geo.y() + geo.height() - new_h

                self.setGeometry(new_x, new_y, new_w, new_h)

            elif self.resize_edge == 'top-right':
                new_y = pos.y()
                new_h = geo.y() + geo.height() - new_y
                new_w = pos.x() - geo.x()

                if new_w < min_width:
                    new_w = min_width
                if new_h < min_height:
                    new_h = min_height
                    new_y = geo.y() + geo.height() - new_h

                self.setGeometry(geo.x(), new_y, new_w, new_h)

            elif self.resize_edge == 'bottom-left':
                new_x = pos.x()
                new_w = geo.x() + geo.width() - new_x
                new_h = pos.y() - geo.y()

                if new_w < min_width:
                    new_w = min_width
                    new_x = geo.x() + geo.width() - new_w
                if new_h < min_height:
                    new_h = min_height

                self.setGeometry(new_x, geo.y(), new_w, new_h)

            elif self.resize_edge == 'bottom-right':
                new_w = pos.x() - geo.x()
                new_h = pos.y() - geo.y()

                if new_w < min_width:
                    new_w = min_width
                if new_h < min_height:
                    new_h = min_height

                self.resize(new_w, new_h)

            elif self.resize_edge == 'left':
                new_x = pos.x()
                new_w = geo.x() + geo.width() - new_x

                if new_w < min_width:
                    new_w = min_width
                    new_x = geo.x() + geo.width() - new_w

                self.setGeometry(new_x, geo.y(), new_w, geo.height())

            elif self.resize_edge == 'right':
                new_w = pos.x() - geo.x()

                if new_w < min_width:
                    new_w = min_width

                self.resize(new_w, geo.height())

            elif self.resize_edge == 'top':
                new_y = pos.y()
                new_h = geo.y() + geo.height() - new_y

                if new_h < min_height:
                    new_h = min_height
                    new_y = geo.y() + geo.height() - new_h

                self.setGeometry(geo.x(), new_y, geo.width(), new_h)

            elif self.resize_edge == 'bottom':
                new_h = pos.y() - geo.y()

                if new_h < min_height:
                    new_h = min_height

                self.resize(geo.width(), new_h)

            self.update_widget_positions()

        elif self.old_position:
            delta = event.globalPos() - self.old_position
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_position = event.globalPos()
        else:
            margin = 5
            pos = event.pos()
            rect = self.rect()
            if pos.x() < margin and pos.y() < margin:
                self.setCursor(QtCore.Qt.SizeFDiagCursor)
            elif pos.x() > rect.width() - margin and pos.y() < margin:
                self.setCursor(QtCore.Qt.SizeBDiagCursor)
            elif pos.x() < margin and pos.y() > rect.height() - margin:
                self.setCursor(QtCore.Qt.SizeBDiagCursor)
            elif pos.x() > rect.width() - margin and pos.y() > rect.height() - margin:
                self.setCursor(QtCore.Qt.SizeFDiagCursor)
            elif pos.x() < margin:
                self.setCursor(QtCore.Qt.SizeHorCursor)
            elif pos.x() > rect.width() - margin:
                self.setCursor(QtCore.Qt.SizeHorCursor)
            elif pos.y() < margin:
                self.setCursor(QtCore.Qt.SizeVerCursor)
            elif pos.y() > rect.height() - margin:
                self.setCursor(QtCore.Qt.SizeVerCursor)
            else:
                self.setCursor(QtCore.Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_position = None
            self.resizing = False
            self.resize_edge = None

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
if not is_admin():
    msg_box = QtWidgets.QMessageBox()
    msg_box.setIcon(QtWidgets.QMessageBox.Question)
    msg_box.setWindowTitle("Administrator Privileges Required")
    msg_box.setText(
        "This application requires administrative privileges to scan all directories.\n"
        "Would you like to restart with admin or run a limited search?"
    )

    restart_button = msg_box.addButton("Restart", QtWidgets.QMessageBox.AcceptRole)
    limited_button = msg_box.addButton("Limited Search", QtWidgets.QMessageBox.RejectRole)
    msg_box.exec_()

    if msg_box.clickedButton() == restart_button:
        try:
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Error",
                f"Failed to elevate privileges: {e}",
            )
        sys.exit()

    app.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))
    window = RoundedWindow()
    window.show()
    sys.exit(app.exec_())