from model.model import Model
from controller.controller import Controller
from view.start_gui import GUInterface
from operator_mod.operator_mod import OperatorModerator

from operator_mod.eventbus.event_handler import EventManager

class ApplicationCoordinator:

    _instance = None
    
    def __new__(cls):

        if cls._instance is None:
            cls._instance = super(ApplicationCoordinator, cls).__new__(cls)
        return cls._instance

    def __init__(self):

        # Safeguard to make sure that the shutdown is working
        self._shutdown_done = False

        # Starts the controller parts: EventBus, InMemDataStore and more
        self.startup()

    def startup(self):

        self.model = Model()
        self.model.start_model()

        self.controller = Controller()
        self.controller.start_controller()

        ope = OperatorModerator()
        ope.start_operator()
        
        # At last we register the Events
        self.events = EventManager.get_instance()
        self.events.add_listener(self.events.EventKeys.APPLICATION_SHUTDOWN, self.shutdown, 0)
        
        # Start the GUI
        self.gui = GUInterface()
        self.gui.start_gui()

    def shutdown(self):
        if self._shutdown_done:
            return
        self._shutdown_done = True

        try:
            print("🧪 [ApplicationCoordinator] Entering GUI shutdown.")
            self.gui.shutdown()
            print("✅ [ApplicationCoordinator] GUI shutdown completed.")
        except Exception as e:
            print(f"❌ [ApplicationCoordinator] Exception during GUI shutdown: {e}")


if __name__ == "__main__":

    Appcoor = ApplicationCoordinator()