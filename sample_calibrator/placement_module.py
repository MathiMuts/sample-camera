# placement_module.py

"""
This file defines the second UI screen (`PlacementFrame`) for the application.

Its purpose is to take the three calibration points from the previous step and
use them to calculate the position, size, and rotation of a target rectangle.
This calculated rectangle is drawn over the live video feed, allowing the user
to visually confirm that the calibration was successful. The user can then
either confirm the placement to proceed or go back to re-calibrate.
"""

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
from itertools import combinations
from . import ui_components

COLOR_RECTANGLE = (0, 255, 0) # BGR

class PlacementFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        self.controller = controller
        self.cap = cap
        self.ui_state = None
        self.final_rectangle_box = None
        self._is_active = False

        self.display_scale = 1.0
        self.pad_x = 0
        self.pad_y = 0
        
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.video_label = tk.Label(self, borderwidth=0, highlightthickness=0, bg="black")
        self.video_label.grid(row=0, column=0, sticky="nsew")

        sidebar_config = {
            'buttons': [
                {'text': 'Back', 'command': self.on_back},
                {'text': 'Confirm', 'command': self.on_next},
            ]
        }
        instructions = (
            "Confirm the green rectangle is correct.\n\n"
            "If not, go 'Back' to re-calibrate.\n\n"
            "Zoom: Mouse Wheel\n"
            "Pan: Middle-Click Drag"
        )
        sidebar = ui_components.UISidebar(self, "Step 2: Placement", instructions, sidebar_config)
        sidebar.grid(row=0, column=1, sticky="ns")

        self.video_label.bind("<ButtonPress-2>", self.on_mouse_event)
        self.video_label.bind("<ButtonRelease-2>", self.on_mouse_event)
        self.video_label.bind("<B2-Motion>", self.on_mouse_event)
        self.video_label.bind("<MouseWheel>", self.on_mouse_event)

    def on_show(self):
        self._is_active = True
        ret, frame = self.cap.read()
        if ret:
            frame_h, frame_w, _ = frame.shape
            self.ui_state = ui_components.BaseUIState(frame_w, frame_h)
        self.video_loop()

    def on_hide(self):
        self._is_active = False

    def video_loop(self):
        if not self._is_active or self.ui_state is None: return

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
            
            self.final_rectangle_box = _calculate_and_draw_rectangle(drawing_frame, self.controller.calibrated_points)
            
            M = np.array([[self.ui_state.zoom, 0, -self.ui_state.pan_offset[0] * self.ui_state.zoom],
                          [0, self.ui_state.zoom, -self.ui_state.pan_offset[1] * self.ui_state.zoom]])
            view_frame = cv2.warpAffine(drawing_frame, M, (self.ui_state.frame_width, self.ui_state.frame_height))
            
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

        event_map = {
            tk.EventType.ButtonPress: cv2.EVENT_MBUTTONDOWN,
            tk.EventType.ButtonRelease: cv2.EVENT_MBUTTONUP,
            tk.EventType.Motion: cv2.EVENT_MOUSEMOVE,
            tk.EventType.MouseWheel: cv2.EVENT_MOUSEWHEEL,
        }

        cv2_event = event_map.get(event.type)
        if cv2_event is not None:
            flags = event.delta if cv2_event == cv2.EVENT_MOUSEWHEEL else 0
            ui_components.handle_view_controls(cv2_event, cam_x, cam_y, flags, self.ui_state)

    def on_next(self):
        self.on_hide()
        self.controller.placement_complete('success', self.final_rectangle_box)

    def on_back(self):
        self.on_hide()
        self.controller.placement_complete('back', None)

# --- Calculation functions ---
def _calculate_circumcenter(pts):
    p1, p2, p3 = pts[0], pts[1], pts[2]
    D = 2 * (p1[0] * (p2[1] - p3[1]) + p2[0] * (p3[1] - p1[1]) + p3[0] * (p1[1] - p2[1]))
    if abs(D) < 1e-6: return None
    ux = ((p1[0]**2 + p1[1]**2) * (p2[1] - p3[1]) + (p2[0]**2 + p2[1]**2) * (p3[1] - p1[1]) + (p3[0]**2 + p3[1]**2) * (p1[1] - p2[1])) / D
    ux = ux * 1.01
    uy = ((p1[0]**2 + p1[1]**2) * (p3[0] - p2[0]) + (p2[0]**2 + p2[1]**2) * (p1[0] - p3[0]) + (p3[0]**2 + p3[1]**2) * (p2[0] - p1[0])) / D
    return (int(ux), int(uy))

def _calculate_and_draw_rectangle(frame, points):
    if points is None or len(points) != 3: return None
    pts_np = np.array(points)
    point_pairs = combinations(pts_np, 2)
    distances = [np.linalg.norm(p1 - p2) for p1, p2 in point_pairs]
    average_distance = np.mean(distances)
    scaling_actor = average_distance / 142.408
    side_x, side_y = 130 * scaling_actor, 120 * scaling_actor
    center = _calculate_circumcenter(pts_np)
    if center is None: return None
    sorted_indices = np.argsort(pts_np[:, 0])
    sorted_pts = pts_np[sorted_indices]
    p_mid, p_right = sorted_pts[1], sorted_pts[2]
    dy, dx = p_right[1] - p_mid[1], p_right[0] - p_mid[0]
    angle = np.degrees(np.arctan2(dy, dx)) + 5
    rect = (center, (side_y, side_x), angle)
    box = np.int32(cv2.boxPoints(rect))
    cv2.drawContours(frame, [box], 0, COLOR_RECTANGLE, 2)
    return box