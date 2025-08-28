# sample_calibrator/__main__.py

import cv2
import calibration_module
import placement_module # <-- Import the new module

def initialize_camera():
    """Tries to find and open a camera."""
    # Using 0 is often more reliable for built-in webcams
    cap = cv2.VideoCapture(1) 
    if not cap.isOpened():
        raise RuntimeError("No camera found")
    return cap

def main():
    """Main application workflow, now with multiple states."""
    cap = initialize_camera()
    
    app_state = 'calibration'
    calibrated_points = None

    while app_state not in ['exit', 'done']:
        
        if app_state == 'calibration':
            # --- Call the module to get the three points ---
            calibrated_points = calibration_module.get_three_points(cap)
            
            if calibrated_points:
                app_state = 'placement' # Success, move to the next step
            else:
                print("\nCalibration was cancelled or failed.")
                app_state = 'exit' # User quit or calibration failed

        elif app_state == 'placement':
            # --- Call the placement module ---
            placement_result = placement_module.place_rectangle(cap, calibrated_points)
            
            if placement_result == 'success':
                print("\nPlacement confirmed. Workflow complete.")
                app_state = 'done' # Success, finish the workflow
            elif placement_result == 'back':
                app_state = 'calibration' # User clicked 'Back', loop again
            else:
                print("\nPlacement was cancelled.")
                app_state = 'exit' # User quit

    # --- Cleanup ---
    print("Closing application.")
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()