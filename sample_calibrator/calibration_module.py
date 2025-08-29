# calibration_module.py

"""
This file defines the first UI screen (`CalibrationFrame`) for the application.

Its main responsibility is to display the live camera feed and allow the user
to select exactly three points by clicking on the video. These points are used
in the next step to establish a coordinate system. The frame also provides
interactive pan (middle-click drag) and zoom (mouse wheel) functionality
for precise point placement.
"""

import tkinter as tk
import cv2
import numpy as np
from PIL import Image, ImageTk
from . import ui_components

COLOR_POINT = (40, 40, 240) # BGR

class CalibrationFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        
        self.controller = controller
        self.cap = cap
        self.ui_state = None
        self.points = []
        self._is_active = False # Flag to control the video loop to save resources.
        
        self.columnconfigure(0, weight=1) 
        self.rowconfigure(0, weight=1)

        self.video_label = tk.Label(self, borderwidth=0, highlightthickness=0, anchor=tk.NW)
        self.video_label.grid(row=0, column=0, sticky="nsew")

        self.status_text = tk.StringVar(value="Points Selected: 0/3")
        sidebar_config = {
            'status_label': {'textvariable': self.status_text},
            'buttons': [{'text': 'Next', 'command': self.on_next}]
        }
        instructions = (
            "Click on the three designated corners.\n\n"
            "Zoom: Mouse Wheel\n"
            "Pan: Middle-Click Drag\n"
            "Remove Point: Right-Click"
        )
        
        sidebar = ui_components.UISidebar(
            parent=self, 
            title="Step 1: Calibrate", 
            instructions=instructions, 
            widgets_config=sidebar_config,
            image_path="help-image-calibration.png"
        )
        sidebar.grid(row=0, column=1, sticky="ns")

        self.next_button = sidebar.created_widgets['Next']
        self.next_button.config(state="disabled")

        # Bind all necessary mouse events to a single handler.
        self.video_label.bind("<Button>", self.on_mouse_event)
        self.video_label.bind("<ButtonRelease-2>", self.on_mouse_event)
        self.video_label.bind("<B2-Motion>", self.on_mouse_event)
        self.video_label.bind("<MouseWheel>", self.on_mouse_event)

    def on_show(self):
        self._is_active = True
        # If returning to this screen, reload the previously selected points.
        if self.controller.calibrated_points:
            self.points = list(self.controller.calibrated_points)
        else:
            self.points = []
        ret, frame = self.cap.read()
        if ret:
            frame_h, frame_w, _ = cv2.flip(frame, -1).shape
            self.ui_state = ui_components.BaseUIState(frame_w, frame_h)
        self.update_ui()
        self.video_loop()

    def on_hide(self):
        self._is_active = False

    def video_loop(self):
        if not self._is_active or not self.ui_state: return
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, -1)
            drawing_frame = frame.copy()
            # Create an affine transformation matrix from the current zoom and pan state.
            M = np.array([[self.ui_state.zoom, 0, -self.ui_state.pan_offset[0] * self.ui_state.zoom],
                          [0, self.ui_state.zoom, -self.ui_state.pan_offset[1] * self.ui_state.zoom]])
            view_frame = cv2.warpAffine(drawing_frame, M, (self.ui_state.frame_width, self.ui_state.frame_height))
            for (px, py) in self.points:
                # Calculate the on-screen position of each point after zoom/pan.
                disp_x = int((px - self.ui_state.pan_offset[0]) * self.ui_state.zoom)
                disp_y = int((py - self.ui_state.pan_offset[1]) * self.ui_state.zoom)
                cv2.circle(view_frame, (disp_x, disp_y), 5, COLOR_POINT, -1)
                cv2.circle(view_frame, (disp_x, disp_y), 5, (255, 255, 255), 1)
            img = cv2.cvtColor(view_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img)
            self.imgtk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.config(image=self.imgtk)
        self.after(15, self.video_loop)

    def on_mouse_event(self, event):
        if self.ui_state is None: return
        if event.num == 1 and event.type == tk.EventType.ButtonPress: # Left-click
            if len(self.points) < 3:
                point_on_frame = ui_components.handle_view_controls(cv2.EVENT_LBUTTONDOWN, event.x, event.y, 0, self.ui_state)
                self.points.append((point_on_frame[0], point_on_frame[1]))
                self.update_ui()
        elif event.num == 3 and event.type == tk.EventType.ButtonPress: # Right-click
            point_on_frame = ui_components.handle_view_controls(cv2.EVENT_RBUTTONDOWN, event.x, event.y, 0, self.ui_state)
            # Make the clickable radius for deleting a point smaller when zoomed in.
            detection_radius = 15 / self.ui_state.zoom
            point_to_remove = next((p for p in self.points if np.linalg.norm(np.array(p) - point_on_frame) < detection_radius), None)
            if point_to_remove:
                self.points.remove(point_to_remove)
                self.update_ui()
        else: # Handle Pan/Zoom
            # Map Tkinter event types to OpenCV event constants for the handler.
            event_map = {tk.EventType.ButtonPress: cv2.EVENT_MBUTTONDOWN,
                         tk.EventType.ButtonRelease: cv2.EVENT_MBUTTONUP,
                         tk.EventType.Motion: cv2.EVENT_MOUSEMOVE,
                         tk.EventType.MouseWheel: cv2.EVENT_MOUSEWHEEL}
            cv2_event = event_map.get(event.type, -1)
            if cv2_event != -1:
                flags = event.delta if cv2_event == cv2.EVENT_MOUSEWHEEL else 0
                ui_components.handle_view_controls(cv2_event, event.x, event.y, flags, self.ui_state)

    def update_ui(self):
        self.status_text.set(f"Points Selected: {len(self.points)}/3")
        self.next_button.config(state="normal" if len(self.points) == 3 else "disabled")

    def on_next(self):
        self.on_hide()
        self.controller.calibration_complete(self.points)