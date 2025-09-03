# __main__.py

"""
This is the main entry point for the Sample Calibrator application.

It performs the following key functions:
1.  Initializes the main Tkinter window (`Application` class).
2.  Finds and initializes the camera, setting the window size based on the
    camera's native resolution.
3.  Manages a dictionary of all UI "frames" (pages), such as calibration,
    placement, and sample positioning.
4.  Acts as the central "controller", holding shared state data (e.g.,
    calibration points) and handling navigation between the different frames.
5.  Ensures the camera is released properly when the application is closed.
"""

import tkinter as tk
import cv2
from tkinter import messagebox

# Import the new frame-based modules
from . import calibration_module
from . import placement_module
from . import positions_module
from .ui_components import SIDEBAR_WIDTH

class Application(tk.Tk):
    """Main application class that manages the window, state, and frames."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Sample Calibrator")

        # --- CHANGE: Set to fullscreen ---
        self.attributes('-fullscreen', True) 

        # --- Camera Initialization ---
        self.cap = self.initialize_camera()
        if not self.cap:
            messagebox.showerror("Camera Error", "Could not open video stream. Please check camera connection.")
            self.destroy()
            return

        # --- REMOVED: Resizing and geometry logic ---
        # The dynamic window sizing, aspect ratio enforcement, and resizable bindings
        # have been removed as they are not needed in fullscreen mode.
        
        # --- Application Data ---
        # State shared between different frames.
        self.calibrated_points = None
        self.final_rectangle_corners = None

        # --- Main Container ---
        container = tk.Frame(self, borderwidth=0, highlightthickness=0)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)


        # --- Frame Management ---
        self.frames = {}
        for F in (calibration_module.CalibrationFrame,
                  placement_module.PlacementFrame,
                  positions_module.SamplePositionsFrame):
            page_name = F.__name__
            # Pass the controller (self) and camera to each frame
            frame = F(parent=container, controller=self, cap=self.cap)
            self.frames[page_name] = frame
            # Stack all frames in the same grid cell; we'll raise the one we want to see.
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("CalibrationFrame")

        # Ensure camera is released on close via the window's close button.
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- REMOVED: on_resize method is no longer needed ---

    def initialize_camera(self):
        """Tries to find and open a camera."""
        # Try common camera indices
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"Success: Camera found on index {i}.")
                return cap
        print("Error: No camera found.")
        return None

    def show_frame(self, page_name):
        """Show a frame for the given page name and start its video loop."""
        frame = self.frames[page_name]
        # Call a method on the frame to let it know it's being shown.
        if hasattr(frame, 'on_show'):
            frame.on_show()
        frame.tkraise()

    def on_closing(self):
        """Handle window closing event."""
        print("Closing application.")
        if self.cap:
            self.cap.release()
        self.destroy()

    # --- State Transition Callbacks ---
    def calibration_complete(self, points):
        if points:
            print("Calibration complete. Points:", points)
            self.calibrated_points = points
            self.show_frame("PlacementFrame")
        else:
            self.on_closing()

    def placement_complete(self, status, rectangle_data):
        if status == 'success':
            print("Placement confirmed.")
            self.final_rectangle_corners = rectangle_data
            self.show_frame("SamplePositionsFrame")
        elif status == 'back':
            self.show_frame("CalibrationFrame")
        else: # Cancelled
            self.on_closing()

    def sample_positions_complete(self, status):
        if status == 'success':
            print("Workflow complete. Final data available.")
            self.on_closing()
        elif status == 'back':
            self.show_frame("PlacementFrame")
        else: # Cancelled
            self.on_closing()


if __name__ == "__main__":
    app = Application()
    app.mainloop()