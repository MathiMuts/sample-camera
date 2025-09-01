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
import os

COLOR_POINT = (40, 40, 240) # BGR

class CalibrationFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        
        self.controller = controller
        self.cap = cap
        self.ui_state = None
        self.points = []
        self._is_active = False # Flag to control the video loop to save resources.
        
        self.display_scale = 1.0
        self.pad_x = 0
        self.pad_y = 0

        self.columnconfigure(0, weight=1) 
        self.rowconfigure(0, weight=1)

        self.video_label = tk.Label(self, borderwidth=0, highlightthickness=0, bg="black")
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
            image_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "help-image-calibration.png")
        )
        sidebar.grid(row=0, column=1, sticky="ns")

        self.next_button = sidebar.created_widgets['Next']
        self.next_button.config(state="disabled")

        self.video_label.bind("<Button>", self.on_mouse_event)
        self.video_label.bind("<ButtonRelease-2>", self.on_mouse_event)
        self.video_label.bind("<B2-Motion>", self.on_mouse_event)
        self.video_label.bind("<MouseWheel>", self.on_mouse_event)

    def on_show(self):
        self._is_active = True
        if self.controller.calibrated_points:
            self.points = list(self.controller.calibrated_points)
        else:
            self.points = []
        ret, frame = self.cap.read()
        if ret:
            # Flipping doesn't change shape, so we can get dimensions from raw frame
            cam_h, cam_w, _ = frame.shape
            self.ui_state = ui_components.BaseUIState(cam_w, cam_h)
        self.update_ui()
        self.video_loop()

    def on_hide(self):
        self._is_active = False

    def video_loop(self):
        if not self._is_active or not self.ui_state: return
        
        label_w = self.video_label.winfo_width()
        label_h = self.video_label.winfo_height()

        if label_w < 10 or label_h < 10:
            self.after(15, self.video_loop)
            return

        ret, frame = self.cap.read()
        if ret:
            # --- CHANGE: Flip the camera frame ---
            frame = cv2.flip(frame, -1)
            
            cam_h, cam_w, _ = frame.shape
            drawing_frame = frame.copy()

            M = np.array([[self.ui_state.zoom, 0, -self.ui_state.pan_offset[0] * self.ui_state.zoom],
                          [0, self.ui_state.zoom, -self.ui_state.pan_offset[1] * self.ui_state.zoom]])
            view_frame = cv2.warpAffine(drawing_frame, M, (self.ui_state.frame_width, self.ui_state.frame_height))
            
            for (px, py) in self.points:
                disp_x = int((px - self.ui_state.pan_offset[0]) * self.ui_state.zoom)
                disp_y = int((py - self.ui_state.pan_offset[1]) * self.ui_state.zoom)
                cv2.circle(view_frame, (disp_x, disp_y), 5, COLOR_POINT, -1)
                cv2.circle(view_frame, (disp_x, disp_y), 5, (255, 255, 255), 1)

            self.display_scale = min(label_w / cam_w, label_h / cam_h)
            disp_w = int(cam_w * self.display_scale)
            disp_h = int(cam_h * self.display_scale)
            resized_frame = cv2.resize(view_frame, (disp_w, disp_h), interpolation=cv2.INTER_AREA)

            canvas = np.zeros((label_h, label_w, 3), dtype=np.uint8)
            self.pad_x = (label_w - disp_w) // 2
            self.pad_y = (label_h - disp_h) // 2
            canvas[self.pad_y:self.pad_y+disp_h, self.pad_x:self.pad_x+disp_w] = resized_frame

            img = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img)
            self.imgtk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.config(image=self.imgtk)
            
        self.after(15, self.video_loop)

    def _view_to_cam_coords(self, x, y):
        cam_x = (x - self.pad_x) / self.display_scale
        cam_y = (y - self.pad_y) / self.display_scale
        return cam_x, cam_y

    def on_mouse_event(self, event):
        if self.ui_state is None: return
        
        cam_x, cam_y = self._view_to_cam_coords(event.x, event.y)
        cam_x = np.clip(cam_x, 0, self.ui_state.frame_width - 1)
        cam_y = np.clip(cam_y, 0, self.ui_state.frame_height - 1)

        if event.num == 1 and event.type == tk.EventType.ButtonPress:
            if len(self.points) < 3:
                point_on_frame = ui_components.handle_view_controls(cv2.EVENT_LBUTTONDOWN, cam_x, cam_y, 0, self.ui_state)
                self.points.append((point_on_frame[0], point_on_frame[1]))
                self.update_ui()
        elif event.num == 3 and event.type == tk.EventType.ButtonPress:
            point_on_frame = ui_components.handle_view_controls(cv2.EVENT_RBUTTONDOWN, cam_x, cam_y, 0, self.ui_state)
            detection_radius = 15 / self.ui_state.zoom
            point_to_remove = next((p for p in self.points if np.linalg.norm(np.array(p) - point_on_frame) < detection_radius), None)
            if point_to_remove:
                self.points.remove(point_to_remove)
                self.update_ui()
        else:
            event_map = {tk.EventType.ButtonPress: cv2.EVENT_MBUTTONDOWN,
                         tk.EventType.ButtonRelease: cv2.EVENT_MBUTTONUP,
                         tk.EventType.Motion: cv2.EVENT_MOUSEMOVE,
                         tk.EventType.MouseWheel: cv2.EVENT_MOUSEWHEEL}
            cv2_event = event_map.get(event.type, -1)
            if cv2_event != -1:
                flags = event.delta if cv2_event == cv2.EVENT_MOUSEWHEEL else 0
                ui_components.handle_view_controls(cv2_event, cam_x, cam_y, flags, self.ui_state)

    def update_ui(self):
        self.status_text.set(f"Points Selected: {len(self.points)}/3")
        self.next_button.config(state="normal" if len(self.points) == 3 else "disabled")

    def on_next(self):
        self.on_hide()
        self.controller.calibration_complete(self.points)