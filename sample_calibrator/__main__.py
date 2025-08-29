# sample_calibrator/__main__.py

import cv2
import calibration_module
import placement_module
import sample_positions_module

def initialize_camera():
    """Tries to find and open a camera."""
    cap = cv2.VideoCapture(1) 
    if not cap.isOpened():
        raise RuntimeError("No camera found")
    return cap

def main():
    """Main application workflow, now with multiple states."""
    cap = initialize_camera()
    
    app_state = 'calibration'
    calibrated_points = None
    final_rectangle_corners = None # <-- Variable to store data between states

    while app_state not in ['exit', 'done']:
        
        if app_state == 'calibration':
            calibrated_points = calibration_module.get_three_points(cap)
            
            if calibrated_points:
                app_state = 'placement'
            else:
                print("\nCalibration was cancelled or failed.")
                app_state = 'exit'

        elif app_state == 'placement':
            # MODIFICATION: Expect a tuple (status, data)
            placement_status, rectangle_data = placement_module.place_rectangle(cap, calibrated_points)
            
            if placement_status == 'success':
                print("\nPlacement confirmed.")
                final_rectangle_corners = rectangle_data # <-- Store the corners
                app_state = 'sample_positions' # <-- Move to the new state
            elif placement_status == 'back':
                app_state = 'calibration'
            else:
                print("\nPlacement was cancelled.")
                app_state = 'exit'
        
        # MODIFICATION: Add the new state logic
        elif app_state == 'sample_positions':
            positions_status = sample_positions_module.show_sample_positions(cap, final_rectangle_corners)
            
            if positions_status == 'success':
                print("\nSample positions confirmed. Workflow complete.")
                app_state = 'done' # Success, finish the workflow
            elif positions_status == 'back':
                app_state = 'placement' # User clicked 'Back', go to placement
            else:
                print("\nSample position selection was cancelled.")
                app_state = 'exit' # User quit

    # --- Cleanup ---
    print("Closing application.")
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()