
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSlider, QGridLayout, QLabel, QPushButton, QComboBox, QCheckBox
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
import cv2

class ImageDisplay(QWidget):
    
    def __init__(self, image: str | list):
        """A view on an image.

        Args:
            image (str | MatLike): path to an image or the iamge itself
            settings (list) : an settings list to be used on this image
        """
        super().__init__()
        
        self.img = None
        self.img_item = None
        self.path = None
        
        if type(image) is str:
                    
            self.path = image
            self.img = cv2.imread(image, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
            
        else:
            self.img = image
        
    def setupForm(self) -> QWidget:
        
        mainlayout = QVBoxLayout()
        
        self.graphicsview = QGraphicsView()
        self.graphicsview.setBaseSize(150, 450)
        self.graphicsview.setContentsMargins(5, 5, 5, 5)
        
        self.img_scene = QGraphicsScene()
        self.graphicsview.setScene(self.img_scene)

        self.img_item = QGraphicsPixmapItem()
        self.img_scene.addItem(self.img_item)
        
        if self.img is not None:
            # Normalize the 12-bit image to 8-bit
            if self.img.dtype == 'uint16':
                # Assuming the image is 12-bit
                self.img = (self.img / 16).astype('uint8')
                
            # Convert the image from BGR (OpenCV) to RGB (Qt)
            image = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)

            # Making the image accessible for Qt
            height, width, _ = image.shape
            bytes_per_line = 3 * width
            q_image = QImage(image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)

            pixmap = QPixmap.fromImage(q_image)
            self.img_item.setPixmap(pixmap)

            self._schedule_fit()

              
        mainlayout.addWidget(self.graphicsview)
        self.setLayout(mainlayout)
        
        return self
    
    def resizeEvent(self, event: QResizeEvent):
        """Resize event to automatically fit the image to the widget."""
        print(f"[DBG] resizeEvent {event.size().width()}x{event.size().height()}")
        super().resizeEvent(event)
        if self.img_item and not self.img_item.pixmap().isNull():
            self._schedule_fit()

      
    def set_image(self, image: str | list) -> None:
        """Set a new image safely into the display."""
        if isinstance(image, str):
            self.img = cv2.imread(image, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_ANYCOLOR)
        else:
            self.img = image

        if self.img is None:
            return

        if self.img.dtype == 'uint16':
            self.img = (self.img / 16).astype('uint8')

        image_rgb = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)
        height, width, _ = image_rgb.shape
        bytes_per_line = 3 * width
        q_image = QImage(image_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)

        # Just update the existing item
        if self.img_item is None:
            self.img_item = QGraphicsPixmapItem(pixmap)
            self.img_scene.addItem(self.img_item)
        else:
            self.img_item.setPixmap(pixmap)

        self._schedule_fit()

    
    
    def _schedule_fit(self):
        print(f"[DBG] _schedule_fit called. Pending={getattr(self,'_fit_pending',False)}")
        if getattr(self, "_fit_pending", False):
            return
        self._fit_pending = True
        QTimer.singleShot(0, self._do_fit)

    def _do_fit(self):
        print(f"[DBG] _do_fit running. ImgItemNull={self.img_item is None or self.img_item.pixmap().isNull()}")
        self._fit_pending = False
        if self.img_item and not self.img_item.pixmap().isNull():
            # Use itemsBoundingRect for stability
            try:
                self.graphicsview.fitInView(self.img_scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            except Exception as e:
                print(f"[ERROR] fitInView failed: {e}")


      

class ImageDisplaySettings(QWidget):
    
    def __init__(self, image: str | list):
        """A view on an image.

        Args:
            image (str | MatLike): path to an image or the iamge itself
            settings (list) : an settings list to be used on this image
        """
        super().__init__()
        self.img = None
        self.img_item = None
        self.path = None
        # ✅ default settings = [threshold_value_or_-1, blur_name, magnitude_name]
        self.settings: list = [-1, "Gaussian", "2X"]
        
        if type(image) is str:
                    
            self.path = image
            self.img = cv2.imread(image, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
            
        else:
            self.img = image
        
    def setupForm(self) -> QWidget:
        
        mainlayout = QHBoxLayout()
        
        # The image display
        self.graphicsview = QGraphicsView()
        self.graphicsview.setBaseSize(150, 450)
        self.graphicsview.setContentsMargins(5, 5, 5, 5)
        
        self.img_scene = QGraphicsScene()
        self.graphicsview.setScene(self.img_scene)

        self.img_item = QGraphicsPixmapItem()
        self.img_scene.addItem(self.img_item)
        
        if self.img is not None:
            # Normalize the 12-bit image to 8-bit
            if self.img.dtype == 'uint16':
                # Assuming the image is 12-bit
                self.img = (self.img / 16).astype('uint8')
                
            # Convert the image from BGR (OpenCV) to RGB (Qt)
            image = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)

            # Making the image accessible for Qt
            height, width, _ = image.shape
            bytes_per_line = 3 * width
            q_image = QImage(image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)

            pixmap = QPixmap.fromImage(q_image)
            self.img_item.setPixmap(pixmap)

            self._schedule_fit()

        
        # The settings options
        settings_widget = QWidget()
        settings_widget.setMinimumSize(QSize(150, 150))
        settings_layout = QGridLayout()
        settings_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Settings header label
        header_label = QLabel("Processing Settings")
        settings_layout.addWidget(header_label, 0, 0)
        
        # Thresholding Value
        thresh_label = QLabel("Threshold")
        self.thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self.thresh_slider.setTickInterval(32)
        self.thresh_slider.setSingleStep(1)
        self.thresh_slider.setRange(0, 255)
        self.thresh_slider.setValue(128)
        self.thresh_slider.setTickPosition(QSlider.TickPosition.TicksAbove)
        
        self.thresh_slider.valueChanged.connect(lambda: self._thresh_slider_value_changed(self.thresh_slider.value()))
        
        self.thresh_value = QLabel("128")
        self.thresh_value.setMinimumSize(QSize(30, 20))
        
        # Deactivating these in the begging
        self.thresh_slider.setEnabled(False)
        self.thresh_value.setEnabled(False)
        
        self.thresh_auto_checkbox = QCheckBox("Automatic Thresholding")
        self.thresh_auto_checkbox.setChecked(True)
        self.thresh_auto_checkbox.stateChanged.connect(lambda: self._auto_thresh_check(self.thresh_auto_checkbox.isChecked()))
        
        # Blur picker
        blur_label = QLabel("Blur")
        self.blur_picker_box = QComboBox()
        self.blur_picker_box.addItems(["Gaussian", "Median", "Stacked"])

        # Magnitude
        magnitude_label = QLabel("Magnitude")
        self.magnitude_box = QComboBox()
        self.magnitude_box.addItems(["2X", "4X", "10X", "20X", "40X", "100X", "Kamera"])

        # Positioning the widgets
        settings_layout.addWidget(blur_label, 1, 0)
        settings_layout.addWidget(self.blur_picker_box, 1, 1)

        settings_layout.addWidget(thresh_label, 2,  0)
        settings_layout.addWidget(self.thresh_slider, 2, 1)
        settings_layout.addWidget(self.thresh_value, 2, 2)
        
        settings_layout.addWidget(self.thresh_auto_checkbox, 3, 1)

        settings_layout.addWidget(magnitude_label, 4, 0)
        settings_layout.addWidget(self.magnitude_box, 4, 1)
        
        settings_widget.setLayout(settings_layout)
        
        # Apply button
        self.apply_button = QPushButton("Apply")
        self.apply_button.pressed.connect(self._apply_settings)
        
        # Positioning of the apply button
        settings_layout.addWidget(self.apply_button, 5, 1)

        
        # Adding to main
        mainlayout.addWidget(self.graphicsview)
        mainlayout.addWidget(settings_widget)
        self.setLayout(mainlayout)
        
        return self
    
    def resizeEvent(self, event: QResizeEvent):
        """Resize event to automatically fit the image to the widget."""
        print(f"[DBG] resizeEvent {event.size().width()}x{event.size().height()}")
        super().resizeEvent(event)
        if self.img_item and not self.img_item.pixmap().isNull():
            self._schedule_fit()

      
    def set_image(self, image: str | list) -> None:
        print(f"[DBG] set_image called. Image shape={self.img.shape if self.img is not None else None}, dtype={self.img.dtype if self.img is not None else None}")
        """Set a new image safely into the display."""
        if isinstance(image, str):
            self.img = cv2.imread(image, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_ANYCOLOR)
        else:
            self.img = image

        if self.img is None:
            return

        if self.img.dtype == 'uint16':
            self.img = (self.img / 16).astype('uint8')

        image_rgb = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)
        height, width, _ = image_rgb.shape
        bytes_per_line = 3 * width
        q_image = QImage(image_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)

        # Just update the existing item
        if self.img_item is None:
            self.img_item = QGraphicsPixmapItem(pixmap)
            self.img_scene.addItem(self.img_item)
        else:
            self.img_item.setPixmap(pixmap)

        self._schedule_fit()



    
    def _auto_thresh_check(self, state : bool) -> None:
        self.thresh_slider.setEnabled(not state)
        self.thresh_value.setEnabled(not state)
    
    def _thresh_slider_value_changed(self, value : int) -> None:
        self.thresh_value.setText(str(value))


    def _apply_settings(self) -> None:
        self.apply_button.setText("Applied!")

        # Get current settings
        value = -1 if self.thresh_auto_checkbox.isChecked() else int(self.thresh_value.text())
        blur = self.blur_picker_box.currentText()
        magnitude = self.magnitude_box.currentText()

        self.settings = [value, blur, magnitude]

        self.apply_button.setText("Apply")
    
    
    def _schedule_fit(self):
        print(f"[DBG] _schedule_fit called. Pending={getattr(self,'_fit_pending',False)}")
        if getattr(self, "_fit_pending", False):
            return
        self._fit_pending = True
        QTimer.singleShot(0, self._do_fit)

    def _do_fit(self):
        print(f"[DBG] _do_fit running. ImgItemNull={self.img_item is None or self.img_item.pixmap().isNull()}")
        self._fit_pending = False
        if self.img_item and not self.img_item.pixmap().isNull():
            # Use itemsBoundingRect for stability
            try:
                self.graphicsview.fitInView(self.img_scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            except Exception as e:
                print(f"[ERROR] fitInView failed: {e}")

