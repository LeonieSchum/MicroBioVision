from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QMessageBox, QStatusBar
from PySide6.QtGui import QCloseEvent, QFont

from operator_mod.eventbus.event_handler import EventManager

from view.main.menubar.menubar import MenuBar
from view.main.middle_interactable.middle_interactable import MiddleInteractable
from controller.algorithms.pellet_sorter.pellet_sorter_gui import PelletSorterApp

class MainWindow(QMainWindow):

    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        Create a new instance of GUIMainFrame if one does not exist yet.
        """
        if cls._instance is None:
            cls._instance = super(MainWindow, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):

        super().__init__()

        self.events = EventManager.get_instance()   
        self.events.add_listener(self.events.EventKeys.STATUS_BAR_UPDATE, self.update_status_bar, 0, True)
        
        self.setupMainUI()

    def setupMainUI(self):

        self.setWindowTitle("Welcome to BioVision")

        # Menubar at top and statusbar at bottom
        
        # The general layout is: left interactable | MDI Area

        # General themes: Font, Colorspace, Borders etc.
        self.app_font = QFont("Yu Gothic UI")
        self.app_font.setPointSize(9)

        self.setFont(self.app_font)
        self.setContentsMargins(5, 5, 5, 5)

        # Creates the MenuBar at the top
        self.menuclass = MenuBar()
        self.menubar = self.menuclass.menuBar()
        self.setMenuBar(self.menubar)
        
        # The Status Bar at bottom
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # This main layout stores three sublayouts (left, middle, right)
        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout()
        self.main_widget.setLayout(self.main_layout)

        # Middle Layout
        ## Contains the MDIArea for main interactions and an inspector that is a console-like
        self.middle_int = MiddleInteractable()
        self.middle_layout = self.middle_int.interactable()        

        # Final
        self.main_layout.addLayout(self.middle_layout)
        self.setCentralWidget(self.main_widget)


    def update_status_bar(self, message: str):
        self.status.showMessage(message, 3000)

    def closeEvent(self, event: QCloseEvent) -> None:
        
        try:
            reply = QMessageBox.question(self, "Exit.", "Are you sure you want to exit?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                self.middle_layout.mdi_area.closeAllSubWindows()
                
                # General Application Shutdown
                try:
                    self.events.trigger_event(self.events.EventKeys.APPLICATION_SHUTDOWN)
                except Exception as e:
                    print("⚠️ Error during shutdown event:", e)
                    
                event.accept()
            else:
                event.ignore()
            
        except Exception:
            pass

    @classmethod
    def get_instance(cls):
        return cls._instance