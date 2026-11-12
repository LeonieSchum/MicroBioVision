
import datetime
from abc import ABC, abstractmethod

from model.utils.resource_manager import ResourceManager
from operator_mod.logger.global_logger import Logger
from operator_mod.in_mem_storage.in_memory_data import InMemoryData
from controller.algorithms.data_writer.data_writer import DataWriter

# Abstract State Class
class State(ABC):
    
    def __init__(self, instance, runtime):
        
        self.data = InMemoryData()
        self.logger = Logger("Algorithm Manager").logger
        self.res_man = ResourceManager()
                
        self.alg_data_writer = DataWriter()

        # This stack contains all images that need to be processed
        self.img_stack = []
        self.stacked_images = set()
        self.processed_images = set()
            
        self.instance = instance
        self.runtime_target = datetime.datetime.now() + datetime.timedelta(seconds=runtime)
        self.terminated = False

    def run(self):
        try:
            self.logger.info("Trying to run the logic of state.")
            self.run_logic()
        except Exception as e:
            self.logger.error(f"Exception in Algorithm Manager: {e}.", exc_info=True)
        finally:
            self.logger.info("Finished a state.")
 
    @abstractmethod
    def run_logic(self):
        pass

    def get_resources(self, resourcespace: str) -> None:
        """Adds resources from a specified resource space to a img_stack (list).

        Args:
            resourcespace (str): name of the resourcespace
        """
        try:
            # Using the new Reasource Manager here
            paths = self.res_man.get_registered_resources(resourcespace, False, True)

            if paths:
                for path in paths:
                    if path not in self.stacked_images:
                        self.img_stack.append(path)
                        self.stacked_images.add(path)

        except Exception as e:
            self.logger.warning(f"Error - Algorithm Manger could not check in resource manager: {e}")

    def terminate(self):
        self.terminated = True