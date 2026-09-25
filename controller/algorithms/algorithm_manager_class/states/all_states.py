from concurrent.futures import ProcessPoolExecutor, as_completed
import gc
from controller.algorithms.pellet_sizer.pellet_sizer import PelletSizer
from controller.algorithms.algorithm_manager_class.states.state_baseclass import State

class PelletSizerSingleState(State):
    
    def run_logic(self):
        
        reference = self.data.get_data(self.data.Keys.PELLET_SIZER_WIDGET_REFERENCE, self.data.Namespaces.DEFAULT)
        self.target_paths = self.data.get_data(self.data.Keys.PELLET_SIZER_IMAGES, self.data.Namespaces.DEFAULT)
        self.target_settings = self.data.get_data(self.data.Keys.PELLET_SIZER_IMAGE_SETTINGS, self.data.Namespaces.DEFAULT)

        # Limit parallel workers based on available RAM
        # 35 MB raw + ~110 MB during processing per image → 4 workers ≈ 500 MB peak
        MAX_WORKERS = 4

        total = len(self.target_paths)
        results = [None] * total  # Pre-allocate to preserve order
        
        reference._progressbar_update(0.2)

        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            try:
                # Submit with index to preserve result order
                future_to_index = {
                    executor.submit(
                        _process_single,  # module-level function (required for pickling)
                        path,
                        self.target_settings[i]
                    ): i
                    for i, path in enumerate(self.target_paths)
                }

                completed = 0
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        results[index] = future.result()
                    except Exception as e:
                        self.logger.error(f"Error on image {index}: {e}")
                        results[index] = None
                    finally:
                        del future_to_index[future]  # Release future immediately
                        gc.collect()

                    completed += 1
                    # Smooth progress from 0.2 to 0.9
                    progress = 0.2 + (completed / total) * 0.7
                    reference._progressbar_update(progress)

            except Exception as e:
                self.logger.error(f"Error occurred in pellet sizer: {e}.")

        self.data.add_data(self.data.Keys.PELLET_SIZER_RESULT, results, self.data.Namespaces.DEFAULT)
        reference.pellet_sizing_done.emit()


# Must be at module level for ProcessPoolExecutor pickling
def _process_single(path: str, settings) -> dict:
    import gc
    from controller.algorithms.pellet_sizer.pellet_sizer import PelletSizer
    sizer = PelletSizer()
    try:
        result = sizer.processing(path, visualization=True, settings=settings)
        return result
    finally:
        del sizer
        gc.collect()