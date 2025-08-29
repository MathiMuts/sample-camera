# app.py

import tkinter as tk
from tkinter import ttk
import cv2

# Import the new frame-based modules
import calibration_module
import placement_module
import sample_positions_module

class Application(tk.Tk):
    """Main application class that manages the window, state, and frames."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Sample Calibrator")
        self.geometry("1200x800")

        # --- Application Data ---
        self.calibrated_points = None
        self.final_rectangle_corners = None
        
        # --- Camera Initialization ---
        self.cap = self.initialize_camera()
        if not self.cap:
            self.destroy()
            return

        # --- Main Container ---
        container = tk.Frame(self, borderwidth=0, highlightthickness=0)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        # --- Frame Management ---
        self.frames = {}
        for F in (calibration_module.CalibrationFrame, 
                  placement_module.PlacementFrame, 
                  sample_positions_module.SamplePositionsFrame):
            page_name = F.__name__
            # Pass the controller (self) and camera to each frame
            frame = F(parent=container, controller=self, cap=self.cap)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Start with the calibration frame
        self.show_frame("CalibrationFrame")

        # Ensure camera is released on close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def initialize_camera(self):
        """Tries to find and open a camera."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: No camera found on index 1.")
            return None
        return cap

    def show_frame(self, page_name):
        """Show a frame for the given page name and start its video loop."""
        frame = self.frames[page_name]
        # Call a method on the frame to let it know it's being shown
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
            # Here you would save the data or proceed
            self.on_closing()
        elif status == 'back':
            self.show_frame("PlacementFrame")
        else: # Cancelled
            self.on_closing()


if __name__ == "__main__":
    app = Application()
    app.mainloop()