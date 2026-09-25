
import cv2


import numpy as np

class PostProcessing:

    def __init__(self, contours, img, settings=None):
        
        self.img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        self.contours = contours
        
        self.result = []
        # Conversion factors (pixel → micrometer)
        self.scale_factors = {
            "2X": 4.5088,    # double of 4X
            "4X": 2.2544,    # your base case
            "10X": 0.90176,  # 4X/2.5
            "20X": 0.45088,  # 4X/5
            "40X": 0.22544,  # 4X/10
            "100X": 0.090176, # 4X/25
            "Kamera": 1.0 
        }

        # Default magnification
        self.magnification = "4X"

        try:
            if settings:
                chosen_mag = settings[2] if len(settings) > 2 else None
                if chosen_mag in self.scale_factors:
                    self.magnification = chosen_mag
        except Exception as e:
            print(f"[Warning] Failed to read magnification from settings: {e}. Falling back to 4X.")


        # Use correct scale factor
        self.pixel_to_um = self.scale_factors[self.magnification]
        
    def postprocess(self):
        
        for i, contour in enumerate(self.contours):
            
            result = self.pellet_processor(contour, i+1)
            self.result.append(result)
            
        
        return self.result, self.img        
    
    def pellet_processor(self, contour, number: int) -> list:
        """Marks all pellets with a number and calculates the results."""

        # Puts a number to the pellets
        x, y, _, _ = cv2.boundingRect(contour)
        xi, yi = self.img.shape[0:2]
        
        larger_dimension = xi if xi > yi else yi
        
        if larger_dimension < 2500:
            font_size = 2
            font_thickness = 2
            
        elif larger_dimension < 5000:
            font_size = 4
            font_thickness = 10
        else:
            font_size = 15
            font_thickness = 20
        
        self.img = cv2.putText(self.img, str(number), (x, y), cv2.FONT_HERSHEY_PLAIN, font_size, (0,0,255), font_thickness, cv2.LINE_AA)
        
        # Drawing the contour
        self.img = cv2.drawContours(self.img, [contour], 0, (0,255,0), 2, cv2.LINE_AA)
        
        # Calculating properties
        area = cv2.contourArea(contour) 
        diameter = ( (area*4) / np.pi ) ** 0.5
        perimeter = diameter * np.pi
        # for the max ferets diameter
        hull = cv2.convexHull(contour)
        rect = cv2.minAreaRect(hull)
        (width, height) = rect[1]
        feret_max = max(width, height)
        compactness = diameter / feret_max 

        diametermy = diameter * self.pixel_to_um # Convert to micrometers
        areamy = (diametermy ** 2) * np.pi / 4 # Area in square micrometers
        perimetermy = diametermy * np.pi # Perimeter in micrometers
        volumemy = (diametermy ** 3) * np.pi / 6 # Volume in cubic micrometers
        circularity = perimeter / cv2.arcLength(contour, True) 
        realperimeter = cv2.arcLength(contour, True)* self.pixel_to_um
        feret_max_my = max(width, height)* self.pixel_to_um

        results = [area, diameter, perimeter, areamy, diametermy, perimetermy,realperimeter, feret_max_my, volumemy, circularity, compactness]
        
        return results