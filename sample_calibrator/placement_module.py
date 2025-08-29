# placement_module.py

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
from itertools import combinations
import ui_components

COLOR_RECTANGLE = (0, 255, 0) # BGR

class PlacementFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        self.controller = controller
        self.cap = cap
        self.ui_state = None
        self.final_rectangle_box = None
        self._is_active = False

        # --- Layout ---
        self.columnconfigure(0, weight=1) # Video feed column expands
        self.rowconfigure(0, weight=1)

        # --- Widgets ---
        self.video_label = tk.Label(self, borderwidth=0, highlightthickness=0, anchor=tk.NW)
        self.video_label.grid(row=0, column=0, sticky="nsew")

        # --- Sidebar using UISidebar ---
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

        # --- Mouse Bindings ---
        self.video_label.bind("<ButtonPress-2>", lambda e: self.on_mouse_event(e.x, e.y, e.type))
        self.video_label.bind("<ButtonRelease-2>", lambda e: self.on_mouse_event(e.x, e.y, e.type))
        self.video_label.bind("<B2-Motion>", lambda e: self.on_mouse_event(e.x, e.y, e.type))
        self.video_label.bind("<MouseWheel>", lambda e: self.on_mouse_event(e.x, e.y, e.type, delta=e.delta))

    def on_show(self):
        self._is_active = True
        ret, frame = self.cap.read()
        if ret:
            frame_h, frame_w, _ = cv2.flip(frame, -1).shape
            self.ui_state = ui_components.BaseUIState(frame_w, frame_h)
        self.video_loop()

    def on_hide(self):
        self._is_active = False

    def video_loop(self):
        if not self._is_active: return

        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, -1)
            drawing_frame = frame.copy()
            
            self.final_rectangle_box = _calculate_and_draw_rectangle(drawing_frame, self.controller.calibrated_points)
            
            M = np.array([[self.ui_state.zoom, 0, -self.ui_state.pan_offset[0] * self.ui_state.zoom],
                          [0, self.ui_state.zoom, -self.ui_state.pan_offset[1] * self.ui_state.zoom]])
            view_frame = cv2.warpAffine(drawing_frame, M, (self.ui_state.frame_width, self.ui_state.frame_height))
            
            img = cv2.cvtColor(view_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img)
            self.imgtk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.config(image=self.imgtk)

        self.after(15, self.video_loop)

    def on_mouse_event(self, x, y, event_type, delta=0):
        if self.ui_state is None: return
        event_map = {'5': cv2.EVENT_MBUTTONDOWN, '6': cv2.EVENT_MBUTTONUP, '7': cv2.EVENT_MOUSEMOVE, '38': cv2.EVENT_MOUSEWHEEL}
        cv2_event = event_map.get(str(event_type), cv2.EVENT_MOUSEMOVE)
        flags = delta if cv2_event == cv2.EVENT_MOUSEWHEEL else 0
        ui_components.handle_view_controls(cv2_event, x, y, flags, self.ui_state)

    def on_next(self):
        self.on_hide()
        self.controller.placement_complete('success', self.final_rectangle_box)

    def on_back(self):
        self.on_hide()
        self.controller.placement_complete('back', None)

# --- Calculation functions --- (No changes below this line)
def _calculate_circumcenter(pts):
    p1, p2, p3 = pts[0], pts[1], pts[2]
    D = 2 * (p1[0] * (p2[1] - p3[1]) + p2[0] * (p3[1] - p1[1]) + p3[0] * (p1[1] - p2[1]))
    if abs(D) < 1e-6: return None
    ux = ((p1[0]**2 + p1[1]**2) * (p2[1] - p3[1]) + (p2[0]**2 + p2[1]**2) * (p3[1] - p1[1]) + (p3[0]**2 + p3[1]**2) * (p1[1] - p2[1])) / D
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
    angle = np.degrees(np.arctan2(dy, dx)) + 5.25
    rect = (center, (side_y, side_x), angle)
    box = np.int32(cv2.boxPoints(rect))
    cv2.drawContours(frame, [box], 0, COLOR_RECTANGLE, 2)
    return box