from PySide6.QtWidgets import QMenu, QMenuBar, QMdiSubWindow
from PySide6.QtGui import QAction
from PySide6.QtCore import QTimer

from model.utils.SQL.sql_manager import SQLManager

from operator_mod.eventbus.event_handler import EventManager
from operator_mod.in_mem_storage.in_memory_data import InMemoryData

from controller.algorithms.pellet_sorter.pellet_sorter_gui import PelletSorterApp

class MenuBar(QMenuBar):

    def __init__(self):

        super().__init__()

        self.events = EventManager()
        self.data = InMemoryData()
        self.sql = SQLManager()
        
        self.project_open = None
        
        self.timer = QTimer()
        self.timer.start(250)

    def menuBar(self):

        # Adding all the action(s)
        
        # First the "File" menu for new projects, measurements and more
        self.menuProject = QMenu("Project", self)


        # The single image analysis tool
        self.single_image_analysis = QAction("Image Analysis", self)
        self.single_image_analysis.triggered.connect(self.single_image_analysis_action)

        self.pellet_analysis = QAction("Image Sorter for Pellet Analysis", self)
        self.pellet_analysis.triggered.connect(self.pellet_analysis_action)
        self.menuProject.addAction(self.pellet_analysis)


        self.menuProject.addAction(self.single_image_analysis)

        #self.actionSettings = QAction("Settings", self)
        #self.actionSettings.triggered.connect(self.project_setting)
        #self.menuProject.addAction(self.actionSettings)


        ## Seperator
        self.menuProject.addSeparator()

        ## Settings / Info
        self.actionInfo = QAction("Info", self)

        self.menuProject.addActions([self.actionInfo])
        


        self.addAction(self.menuProject.menuAction())

        

        return self
    

    

    def single_image_analysis_action(self):
        
        from view.main.mainframe import MainWindow
        from view.single_image_analysis.single_image_analysis_form import SingleImageAnylsisForm
        
        main_inst = MainWindow.get_instance()

        single_image_form = SingleImageAnylsisForm()
        single_image_form.setupForm()
        
        subwindow = QMdiSubWindow()
        subwindow.setWidget(single_image_form)
        
        main_inst.middle_layout.mdi_area.addSubWindow(subwindow)
        
        subwindow.show()

    def pellet_analysis_action(self):
        
        from view.main.mainframe import MainWindow
        
        main_inst = MainWindow.get_instance()

        pellet_form = PelletSorterApp()
        
        subwindow = QMdiSubWindow()
        subwindow.setWidget(pellet_form)
        subwindow.setWindowTitle("Image Sorter for Pellet Analysis")
        subwindow.resize(1100, 750)
        main_inst.middle_layout.mdi_area.addSubWindow(subwindow)
        
        # Fenster anzeigen
        subwindow.show()


