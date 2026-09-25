
import csv
import os
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QTableView, QFileDialog, QMessageBox
from PySide6.QtCore import QThread, Signal, QElapsedTimer, QTimer, QSignalBlocker
from PySide6.QtGui import QStandardItemModel, QStandardItem
import time
import cv2
import numpy as np

from view.single_image_analysis.graphics_view_widget import ImageDisplaySettings, ImageDisplay

from controller.algorithms.algorithm_manager_class.algorithm_manager import AlgorithmManager
from operator_mod.in_mem_storage.in_memory_data import InMemoryData
from operator_mod.eventbus.event_handler import EventManager
from operator_mod.logger.global_logger import Logger

class PelletSizeWidghet(QTabWidget):

    pellet_sizing_done = Signal()

    def __init__(self):
        
        super().__init__()
                
        self.data = InMemoryData()
        self.events = EventManager.get_instance()
        
        self.algman = AlgorithmManager.get_instance()
        
        self.logger = Logger("Application").logger   
        
        self.pellet_sizing_done.connect(self.display_results)
        
        # Adding a reference to self into the datastore
        self.data.add_data(self.data.Keys.PELLET_SIZER_WIDGET_REFERENCE, self, self.data.Namespaces.DEFAULT)
        
    def setupForm(self):

        setupWidget = QWidget()
        setuplayout = QVBoxLayout()
        
        ### Image Picker
        # The selector and file path
        selector = QHBoxLayout()
        
        label = QLabel("Choose an image: ")

        calib_dialog_form_button = QPushButton("...")
        calib_dialog_form_button.clicked.connect(self.calib_dialog_button)
        
        selector.addWidget(label)
        selector.addWidget(calib_dialog_form_button)
        
        ### Image Counter
        self.counter = QLabel("Number of selected images: 0")
        
        ### Image Displayer
        imagedisplay_layout = QHBoxLayout()

        imagelayout = QVBoxLayout()
        
        self.imageview = QTabWidget()
        self.imageview.setMinimumSize(400, 600)
        
        delete_image_button = QPushButton("Remove current image from selection")
        delete_image_button.clicked.connect(self._remove_image_button)
        
        imagelayout.addWidget(self.imageview)
        imagelayout.addWidget(delete_image_button)
        
        ### Adding a few custom settings
        
        imagedisplay_layout.addLayout(imagelayout)
        
        # Analyze button and progressbar
        analyze_layout = QVBoxLayout()
        
        startbutton = QPushButton("Analyze")
        startbutton.clicked.connect(self.analyze_button_action)
        
        self.progressbar = QProgressBar()

        analyze_layout.addWidget(startbutton)
        analyze_layout.addWidget(self.progressbar)

        apply_all_button = QPushButton("Apply Current Settings to All")
        apply_all_button.clicked.connect(self._apply_current_settings_to_all)
        analyze_layout.addWidget(apply_all_button)

        
        ### back to welcome page
        back_to_welcome_page_button = QPushButton("Back")
        back_to_welcome_page_button.clicked.connect(lambda: self.events.trigger_event(self.events.EventKeys.SI_FORM_BACK_BUTTON))
        
        # Stitching together
        setuplayout.addLayout(selector)
        setuplayout.addWidget(self.counter)
        setuplayout.addLayout(imagedisplay_layout)
        setuplayout.addLayout(analyze_layout)
        setuplayout.addWidget(back_to_welcome_page_button)
        
        setupWidget.setLayout(setuplayout)
        
        self.addTab(setupWidget, "Setup")
    
    def analyze_button_action(self) -> None:
        """Action for the analyze button. Checks previous results.
        """
        
        from view.main.mainframe import MainWindow
        instance = MainWindow.get_instance()
        
        # First we check for existing tabs 
        if self.count() > 1:
            result =  QMessageBox.information(instance, "Deleting prior Results", "You have prior results in this form. Do you want to continue?", QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
            
            if not result == QMessageBox.StandardButton.Yes:
                return
            
            while self.count() > 1:
                self.removeTab(self.count() - 1)
        
        filepaths = []
        filesettings = []
        filesizes = []
        for i in range(self.imageview.count()):
            widget = self.imageview.widget(i)
            path = widget.path
            if os.path.exists(path):
                filepaths.append(path)
                filesizes.append(os.path.getsize(path))
                #filesizes.append(size)

                # ✅ ensure each tab has settings
                if not getattr(widget, "settings", None):
                    # pull the UI values into .settings
                    if hasattr(widget, "_apply_settings"):
                        widget._apply_settings()

                filesettings.append(widget.settings or [-1, "Gaussian", "2X"])
        
        self.data.add_data(self.data.Keys.PELLET_SIZER_IMAGES, filepaths, self.data.Namespaces.DEFAULT)
        self.data.add_data(self.data.Keys.PELLET_SIZER_IMAGE_SETTINGS, filesettings, self.data.Namespaces.DEFAULT)
        self.algman.add_task(self.algman.States.PELLET_SIZER_SINGLE_STATE, 0)
    
    ### Result logic
    def display_results(self) -> None:
        """Displays results after analyzing. Called from the WaiterThread by a signal.
        """
        self._progressbar_update(1)
        self._progressbar_update(0)
        
        # Fetching results
        results = self.data.get_data(self.data.Keys.PELLET_SIZER_RESULT, self.data.Namespaces.DEFAULT)
        
        images = []
        data = []
        
        for result in results:
            images.append(result["Image"])
            data.append(result["Data"])
        
        # The images come back in the order of the filepaths given
        filepaths = self.data.get_data(self.data.Keys.PELLET_SIZER_IMAGES, self.data.Namespaces.DEFAULT)
        
        # Creating two widget to fit into QTabWidget
        resultimage_widget = self._result_image_widget(images, filepaths)
        result_table = self._result_table(data, filepaths)
        
        self.addTab(resultimage_widget, "Result Images")
        self.addTab(result_table, "Result Values")
        
        ### Deleting the references to the images of the result to clean up the internal data
        self.data.delete_data(self.data.Keys.PELLET_SIZER_RESULT, self.data.Namespaces.DEFAULT)
        
    def _result_image_widget(self, images: list, filepaths: list) -> QWidget:
        try:
            if not images or not filepaths:
                self.logger.critical("No results or no filepaths provided.")
                return QWidget()

            if len(images) != len(filepaths):
                self.logger.critical(
                    f"Result images and given paths do not match. "
                    f"images={len(images)} paths={len(filepaths)}"
                )
            n = min(len(images), len(filepaths))

            widget = QWidget()
            layout = QVBoxLayout()
            save_button = QPushButton("Save and Export")
            save_button.clicked.connect(lambda: self._result_image_export_button(filepaths[:n]))
            self.img_stacked_tab = QTabWidget()

            for i in range(n):
                imgwidget = ImageDisplay(images[i])
                imgwidget.setupForm()
                self.img_stacked_tab.addTab(imgwidget, os.path.basename(filepaths[i]))

            layout.addWidget(self.img_stacked_tab)
            layout.addWidget(save_button)
            widget.setLayout(layout)
            return widget

        except Exception as e:
            self.logger.error(f"Error in setting up image displays for results: {e}.")
            return QWidget()
 
        
        except Exception as e:
            self.logger.error(f"Error in setting up image displays for results: {e}.") 
    
    def _result_image_export_button(self, filepaths: list) -> None:
        """Exports the resulting images (all/current) as .bmp format.

        Args:
            filepaths (list): str path of images input
        """
        
        from view.main.mainframe import MainWindow
        instance = MainWindow.get_instance()
        
        msg_box = QMessageBox(instance)
        msg_box.setWindowTitle("Export Image(s)")
        msg_box.setText("Do you want to export all images, the current one, or abort?")
        msg_box.setIcon(QMessageBox.Icon.Question)

        # Add buttons
        all_button = msg_box.addButton("All", QMessageBox.ButtonRole.AcceptRole)
        current_button = msg_box.addButton("Current", QMessageBox.ButtonRole.ActionRole)
        abort_button = msg_box.addButton("Abort", QMessageBox.ButtonRole.RejectRole)

        # Execute the dialog
        msg_box.exec()
        
        # Handle the user's choice
        if msg_box.clickedButton() == all_button:
            # Exporting the current image
            dir = QFileDialog.getExistingDirectory(instance, "Choose Directory")

            for i in range(self.img_stacked_tab.count()):
                img_widget = self.img_stacked_tab.widget(i)
                image = img_widget.img

                image_basename = os.path.basename(filepaths[i])
                image_basename = os.path.splitext(image_basename)[0]
                filepath = os.path.join(dir, f"result_image_{image_basename}_{i}.bmp")

                cv2.imwrite(filepath, image)
            
            if os.path.exists(filepath):
                QMessageBox.information(instance, "Success", "Exporting successful.", QMessageBox.StandardButton.Ok)
            else:
                QMessageBox.information(instance, "Error", "Error occured. Please try again.", QMessageBox.StandardButton.Ok)
                
        elif msg_box.clickedButton() == current_button:
            
            # Exporting the current image
            dir = QFileDialog.getExistingDirectory(instance, "Choose Directory")

            idx = self.img_stacked_tab.currentIndex()
            img_widget = self.img_stacked_tab.currentWidget()
            image = img_widget.img
            
            if idx <= len(filepaths):
                image_basename = os.path.basename(filepaths[idx])
                image_basename = os.path.splitext(image_basename)[0]
            else:
                image_basename = "missing_basename"
                
            filepath = os.path.join(dir, f"result_image_{image_basename}.bmp")

            cv2.imwrite(filepath, image)
            
            if os.path.exists(filepath):
                QMessageBox.information(instance, "Success", "Exporting successful.", QMessageBox.StandardButton.Ok)
            else:
                QMessageBox.information(instance, "Error", "Error occured. Please try again.", QMessageBox.StandardButton.Ok)
            
        elif msg_box.clickedButton() == abort_button:
            return        
    
    def _result_table(self, data: list, filepaths: list) -> QWidget:
        """Builds a parent Widget to house the TabResultWidget that contains the TableViews for data on image results.

        Args:
            data (list): data from algorithm PELLETSIZER
            filepaths (list): filepaths for used images

        Returns:
            QWidget: parent widget w/ child TabWidget where results are displayed
        """
        
        try:
            widget = QWidget()
            mainlayout = QVBoxLayout()

            self.stacked_result_tab = QTabWidget()

            # Store references to table models for later access
            self.table_models = []

            for idx, image in enumerate(data):
                table = QTableView()
                model = QStandardItemModel()
                model.setHorizontalHeaderLabels(["Area [-]", "(eq) Diameter [-]", "(eq) Perimeter [-]","Area [mym^2]", "(eq) Diameter [mym]","(eq) Perimeter [mym]", "Perimeter [mym]","Feret_max [mym]", "(eq) Volume [mym^3] " , "circularity [-]", "compactness [-]"])

                for result in image:
                    row = []
                    for value in result:
                        row.append(QStandardItem(str(value)))

                    model.appendRow(row)

                table.setModel(model)
                self.table_models.append(model)

                self.stacked_result_tab.addTab(table, str(str(os.path.basename(filepaths[idx]))))

            mainlayout.addWidget(self.stacked_result_tab)

            # Add Save Button
            save_button = QPushButton("Save and Export")
            save_button.clicked.connect(lambda: self._save_result_tables(filepaths))  # Connect to the save function
            mainlayout.addWidget(save_button)

            widget.setLayout(mainlayout)

            return widget
        except Exception as e:
            self.logger.error(f"Error setting up result tables: {e}.")
            
    def _save_result_tables(self, filepaths: list) -> None:
        """Exports result tables (all/current) from the TabWidget View on Results.

        Args:
            filepaths (list): str path from the images that have been analyzed
        """
        
        from view.main.mainframe import MainWindow
        instance = MainWindow.get_instance()
        
        msg_box = QMessageBox(instance)
        msg_box.setWindowTitle("Export Table(s)")
        msg_box.setText("Do you want to export all tables, the current one, or abort?")
        msg_box.setIcon(QMessageBox.Icon.Question)

        # Add buttons
        all_button = msg_box.addButton("All", QMessageBox.ButtonRole.AcceptRole)
        current_button = msg_box.addButton("Current", QMessageBox.ButtonRole.ActionRole)
        abort_button = msg_box.addButton("Abort", QMessageBox.ButtonRole.RejectRole)

        # Execute the dialog
        msg_box.exec()
        
        # Handle user's choice
        if msg_box.clickedButton() == all_button:
            # Export all tables
            save_dir = QFileDialog.getExistingDirectory(instance, "Select Directory to Save All Tables")
            if save_dir:
                
                for idx, model in enumerate(self.table_models):
                    image_basename = os.path.basename(filepaths[idx])
                    image_basename = os.path.splitext(image_basename)[0]
                    
                    file_path = os.path.join(save_dir, f"result_table_{image_basename}.csv")
                    self._export_model_to_csv(model, file_path)

                if os.path.exists(file_path):
                    QMessageBox.information(instance, "Success", "Exporting successful.", QMessageBox.StandardButton.Ok)
                else:
                    QMessageBox.information(instance, "Error", "Error occured. Please try again.", QMessageBox.StandardButton.Ok)

        elif msg_box.clickedButton() == current_button:
            
            # Export current table
            current_index = self.stacked_result_tab.currentIndex()
            if current_index >= 0:
                
                image_basename = os.path.basename(filepaths[current_index])
                image_basename = os.path.splitext(image_basename)[0]
                
                file_path, _ = QFileDialog.getSaveFileName(instance, "Save Current Table", f"result_table_{image_basename}.csv", "CSV Files (*.csv)")
                if file_path:
                    self._export_model_to_csv(self.table_models[current_index], file_path)

                if os.path.exists(file_path):
                    QMessageBox.information(instance, "Success", "Exporting successful.", QMessageBox.StandardButton.Ok)
                else:
                    QMessageBox.information(instance, "Error", "Error occured. Please try again.", QMessageBox.StandardButton.Ok)

        elif msg_box.clickedButton() == abort_button:
            # Abort operation
            return        
    
    def _export_model_to_csv(self, model: QStandardItemModel, file_path: str) -> None:
        """Exports a model to a .csv file.

        Args:
            model (QStandardItemModel): Model with data
            file_path (str): str path that is valid
        """
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)

                # Write headers
                headers = [model.horizontalHeaderItem(col).text() for col in range(model.columnCount())]
                writer.writerow(headers)

                # Write data rows
                for row in range(model.rowCount()):
                    row_data = [model.item(row, col).text() for col in range(model.columnCount())]
                    writer.writerow(row_data)

            self.logger.info(f"Exported table to {file_path}.")
        except Exception as e:
            self.logger.error(f"Error exporting table to {file_path}: {e}.")

    def calib_dialog_button(self) -> None:
        """Fetches a list of files that shall be analyzed.
        """
        from view.main.mainframe import MainWindow
        instance = MainWindow.get_instance()
        
        file_paths, _ = QFileDialog.getOpenFileNames(instance, "Open File", "", 
                                             "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp)")
        
        for file_path in file_paths:
            if os.path.exists(file_path):
                
                # the ImageDisplay holds on to the path so we can later just iterate through all widgets and get the paths for the image analysis
                widget = ImageDisplaySettings(file_path)
                widget.setupForm()
                
                self.imageview.addTab(widget, str(os.path.basename(file_path)))
                
                self.imageview.setCurrentIndex(self.imageview.count() - 1)
                self._change_counter(self.imageview.count())
            else:
                self.logger.warning(f"Filepath invalid: {file_path}")
                 
    ### backend logic
    def _progressbar_update(self, value: float):
        """Progresses the progress bar with a given value.

        Args:
            value (float): Value between 0 and 1.
        """
        print(f"[DBG] _progressbar_update({value})")
        self.progressbar.setValue(int(value * 100))  # Convert to percentage
        self.progressbar.repaint()  # Ensure the UI reflects the change immediately
    
    def _change_counter(self, count: int):
        self.counter.setText(f"Number of selected images: {count}")

    def _remove_image_button(self):
    
        idx = self.imageview.currentIndex()
        
        if idx is not None:
            self.imageview.removeTab(idx)
            self._change_counter(self.imageview.count())
    
    



    def _apply_current_settings_to_all(self):
        print("[DBG] apply_current_settings_to_all START")
        current_tab = self.imageview.currentWidget()
        if not isinstance(current_tab, ImageDisplaySettings):
            return

        current_settings = list(current_tab.settings) if current_tab.settings else [-1, "Gaussian", "2X"]

        def apply_all():
            
            # Freeze repaints while we touch many widgets
            self.imageview.setUpdatesEnabled(False)

            # Temporarily block _schedule_fit and _do_fit methods
            original_schedule_fit = {}
            for i in range(self.imageview.count()):
                tab = self.imageview.widget(i)
                if isinstance(tab, ImageDisplaySettings):
                    original_schedule_fit[tab] = tab._schedule_fit
                    tab._schedule_fit = lambda: None  # temporarily block
            original_do_fit = {}
            for tab in original_schedule_fit.keys():
                original_do_fit[tab] = tab._do_fit
                tab._do_fit = lambda: None  # temporarily block  

            try:
                for i in range(self.imageview.count()):
                    
                    tab = self.imageview.widget(i)
                    print(f"[DBG] Applying settings to tab {i}: {tab.settings}")
                    if not isinstance(tab, ImageDisplaySettings):
                        continue

                    thr, blur, mag = current_settings

                    # Block CHILD signals while we set values
                    b1 = QSignalBlocker(tab.thresh_slider)
                    b2 = QSignalBlocker(tab.thresh_auto_checkbox)
                    b3 = QSignalBlocker(tab.blur_picker_box)
                    b4 = QSignalBlocker(tab.magnitude_box)
                    try:
                        tab.thresh_auto_checkbox.setChecked(thr == -1)
                        if thr == -1:
                            tab.thresh_slider.setEnabled(False)
                            tab.thresh_value.setEnabled(False)
                        else:
                            tab.thresh_slider.setEnabled(True)
                            tab.thresh_value.setEnabled(True)
                            tab.thresh_slider.setValue(int(thr))
                            tab.thresh_value.setText(str(int(thr)))

                        tab.blur_picker_box.setCurrentText(blur)
                        tab.magnitude_box.setCurrentText(mag)
                        tab.settings = [thr, blur, mag]
                    finally:
                        # destroy blockers so signals resume
                        del b1, b2, b3, b4
            finally:
                self.imageview.setUpdatesEnabled(True)
            
            for tab in original_schedule_fit.keys():
                tab._schedule_fit = original_schedule_fit[tab]
                tab._do_fit = original_do_fit[tab]

            QTimer.singleShot(50, lambda: current_tab._schedule_fit())

            # Single, deferred refresh of the whole stack
            #QTimer.singleShot(0, self.imageview.update)

        QTimer.singleShot(10, apply_all)
        
        print("[DBG] apply_current_settings_to_all END (scheduled)")
