# sample_positions_module.py

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
import ui_components

GRID_ROWS, GRID_COLS = 8, 12
COLOR_RECTANGLE_BORDER = (0, 255, 0)
COLOR_GRID_POINT = (255, 100, 0)

class SamplePositionsFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        self.controller = controller
        self.cap = cap
        self.ui_state = None
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
                {'text': 'Save and Finish', 'command': self.on_finish},
            ]
        }
        instructions = "Sample grid is now projected.\n\nReview the final positions."
        sidebar = ui_components.UISidebar(self, "Step 3: Confirmation", instructions, sidebar_config)
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

            _draw_grid_on_rectangle(drawing_frame, self.controller.final_rectangle_corners)

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

    def on_finish(self):
        self.on_hide()
        self.controller.sample_positions_complete('success')
        
    def on_back(self):
        self.on_hide()
        self.controller.sample_positions_complete('back')


# --- Grid Calculation functions --- (No changes below this line)
def _order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s, diff = pts.sum(axis=1), np.diff(pts, axis=1)
    rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]
    rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)]
    return rect

def _draw_grid_on_rectangle(frame, corners):
    if corners is None or len(corners) != 4: return
    src_pts = _order_points(corners)
    dst_w, dst_h = 1200, 1300
    dst_pts = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(dst_pts, src_pts)
    grid_points_dst = []
    x_step, y_step = dst_w / GRID_COLS, dst_h / GRID_ROWS
    for i in range(GRID_ROWS):
        for j in range(GRID_COLS):
            grid_points_dst.append([(j + 0.5) * x_step, (i + 0.5) * y_step])
    grid_points_dst = np.array([grid_points_dst], dtype="float32")
    if grid_points_dst.size > 0:
        grid_points_src = cv2.perspectiveTransform(grid_points_dst, M)
        for pt in grid_points_src[0]:
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 4, COLOR_GRID_POINT, -1)
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 4, (255,255,255), 1)
    cv2.drawContours(frame, [np.int32(corners)], 0, COLOR_RECTANGLE_BORDER, 1)