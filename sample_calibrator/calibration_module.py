# sample_calibrator/calibration_module.py

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
import ui_components # We still use this for BaseUIState and handle_view_controls

COLOR_POINT = (40, 40, 240) # BGR

class CalibrationFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        super().__init__(parent)
        self.controller = controller
        self.cap = cap

        # --- State ---
        self.ui_state = None 
        self.points = []
        
        # --- Layout ---
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Widgets ---
        # Sidebar
        sidebar = tk.Frame(self, width=250, bg="#2d2d2d")
        sidebar.grid(row=0, column=0, sticky="nsw")
        
        # Main content area for video
        self.video_label = tk.Label(self)
        self.video_label.grid(row=0, column=1, sticky="nsew")

        # --- Sidebar Content ---
        lbl_title = tk.Label(sidebar, text="Step 1: Calibrate", font=("Segoe UI", 16), bg="#2d2d2d", fg="white")
        lbl_title.pack(pady=10, padx=10, anchor="w")

        self.lbl_status = tk.Label(sidebar, text="Points Selected: 0/3", font=("Segoe UI", 10), bg="#2d2d2d", fg="white")
        self.lbl_status.pack(pady=5, padx=10, anchor="w")

        instructions = (
            "Click on the three designated corners.\n\n"
            "Zoom: Mouse Wheel\n"
            "Pan: Middle-Click Drag\n"
            "Remove Point: Right-Click"
        )
        lbl_inst = tk.Label(sidebar, text=instructions, justify=tk.LEFT, font=("Segoe UI", 10), bg="#2d2d2d", fg="#cccccc")
        lbl_inst.pack(pady=20, padx=10, fill="x")

        self.next_button = ttk.Button(sidebar, text="Next", command=self.on_next, state="disabled")
        self.next_button.pack(side="bottom", pady=20, padx=10, fill="x")
        
        # --- Mouse Bindings for Video Label ---
        self.video_label.bind("<Button-1>", self.on_mouse_click)
        self.video_label.bind("<Button-3>", self.on_mouse_click)
        self.video_label.bind("<ButtonPress-2>", lambda e: self.on_mouse_event(e.x, e.y, e.type))
        self.video_label.bind("<ButtonRelease-2>", lambda e: self.on_mouse_event(e.x, e.y, e.type))
        self.video_label.bind("<B2-Motion>", lambda e: self.on_mouse_event(e.x, e.y, e.type))
        self.video_label.bind("<MouseWheel>", lambda e: self.on_mouse_event(e.x, e.y, e.type, delta=e.delta))

        # Flag to control the video loop
        self._is_active = False

    def on_show(self):
        """Called by the controller when this frame is shown."""
        self._is_active = True
        self.points = [] # Reset points each time we show this frame
        
        # Initialize UI state with the correct frame dimensions
        ret, frame = self.cap.read()
        if ret:
            frame_h, frame_w, _ = cv2.flip(frame, -1).shape
            self.ui_state = ui_components.BaseUIState(frame_w, frame_h)
        
        self.update_ui()
        self.video_loop()

    def on_hide(self):
        """Called by the controller before switching to another frame."""
        self._is_active = False

    def video_loop(self):
        """Reads a frame, processes it, and displays it."""
        if not self._is_active:
            return

        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, -1)
            
            # Create a drawing copy
            drawing_frame = frame.copy()
            
            # Apply zoom and pan transformations
            M = np.array([[self.ui_state.zoom, 0, -self.ui_state.pan_offset[0] * self.ui_state.zoom],
                          [0, self.ui_state.zoom, -self.ui_state.pan_offset[1] * self.ui_state.zoom]])
            view_frame = cv2.warpAffine(drawing_frame, M, (self.ui_state.frame_width, self.ui_state.frame_height))

            # Draw points on the VIEW frame (after zoom/pan)
            for (px, py) in self.points:
                # Transform original point coords to view coords
                disp_x = int((px - self.ui_state.pan_offset[0]) * self.ui_state.zoom)
                disp_y = int((py - self.ui_state.pan_offset[1]) * self.ui_state.zoom)
                cv2.circle(view_frame, (disp_x, disp_y), 7, COLOR_POINT, -1)
                cv2.circle(view_frame, (disp_x, disp_y), 7, (255, 255, 255), 1)

            # Convert for Tkinter
            img = cv2.cvtColor(view_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img)
            self.imgtk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.config(image=self.imgtk)

        # Schedule the next frame
        self.after(15, self.video_loop)

    def on_mouse_click(self, event):
        """Handle left and right mouse clicks to add/remove points."""
        point_on_frame = self.on_mouse_event(event.x, event.y, event.type)

        if event.num == 1 and len(self.points) < 3: # Left click
            orig_coords = (point_on_frame[0], point_on_frame[1])
            print(f"Added point at: ({orig_coords[0]:.2f}, {orig_coords[1]:.2f})")
            self.points.append(orig_coords)

        elif event.num == 3: # Right click
            detection_radius = 15 / self.ui_state.zoom
            point_to_remove = None
            for p in self.points:
                if np.linalg.norm(np.array(p) - point_on_frame) < detection_radius:
                    point_to_remove = p
                    break
            if point_to_remove:
                self.points.remove(point_to_remove)
                print(f"Removed point near: ({point_to_remove[0]:.2f}, {point_to_remove[1]:.2f})")
        
        self.update_ui()

    def on_mouse_event(self, x, y, event_type, delta=0):
        """Generic handler for zoom/pan events."""
        if self.ui_state is None: return

        # Map Tkinter event types to OpenCV event types for the handler
        event_map = {
            '5': cv2.EVENT_MBUTTONDOWN,
            '6': cv2.EVENT_MBUTTONUP,
            '7': cv2.EVENT_MOUSEMOVE,
            '38': cv2.EVENT_MOUSEWHEEL
        }
        cv2_event = event_map.get(str(event_type), cv2.EVENT_MOUSEMOVE)
        
        # Flags for mouse wheel
        flags = delta if cv2_event == cv2.EVENT_MOUSEWHEEL else 0

        return ui_components.handle_view_controls(cv2_event, x, y, flags, self.ui_state)

    def update_ui(self):
        """Update UI elements based on the current state."""
        self.lbl_status.config(text=f"Points Selected: {len(self.points)}/3")
        self.next_button.config(state="normal" if len(self.points) == 3 else "disabled")

    def on_next(self):
        """Handle Next button click."""
        self.on_hide()
        self.controller.calibration_complete(self.points)