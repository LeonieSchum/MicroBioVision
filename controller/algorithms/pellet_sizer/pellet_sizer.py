import os
import gc
import cv2
from controller.algorithms.pellet_sizer.steps.postprocessing import PostProcessing
from controller.algorithms.pellet_sizer.steps.preprocessing import Preprocessor
from controller.algorithms.pellet_sizer.steps.processing import Processor

class PelletSizer:
    
    def __init__(self) -> None:
        pass
    
    def processing(self, path: str, visualization: bool = False, settings: list = None) -> dict:
        """Processes a given pellet image to analyze for pellet sizes."""
        
        if not os.path.exists(path):
            raise ValueError("Path object does not exist in PelletSizer.")
        
        img = None
        contours = None
        prepro = None
        pro = None
        post = None

        try:
            # Preprocessing
            prepro = Preprocessor(path, settings)
            img = prepro.process()
            del prepro
            prepro = None

            # Processing
            pro = Processor(img)
            contours = pro.process()
            del pro
            pro = None

            # Postprocessing
            post = PostProcessing(contours, img, settings)

            # img and contours are now inside PostProcessing — release our reference
            del img
            del contours
            img = None
            contours = None

            results, image = post.postprocess()
            del post
            post = None

            if visualization:
                return {
                    "Image": image,
                    "Data": results
                }
            else:
                # image is not needed — explicitly release it
                del image
                return {
                    "Data": results
                }

        except Exception as e:
            raise e

        finally:
            # Guarantee cleanup even if an exception occurs
            for obj in [prepro, pro, post, img, contours]:
                del obj
            gc.collect()