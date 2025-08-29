# sample_calibrator/sample_positions_module.py

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
        super().__init__(parent)
        self.controller = controller
        self.cap = cap
        self.ui_state = None
        self._is_active = False

        # --- Layout & Widgets ---
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar = tk.Frame(self, width=250, bg="#2d2d2d")
        sidebar.grid(row=0, column=0, sticky="nsw")
        
        self.video_label = tk.Label(self)
        self.video_label.grid(row=0, column=1, sticky="nsew")

        # --- Sidebar Content ---
        lbl_title = tk.Label(sidebar, text="Step 3: Confirmation", font=("Segoe UI", 16), bg="#2d2d2d", fg="white")
        lbl_title.pack(pady=10, padx=10, anchor="w")

        instructions = "Sample grid is now projected.\n\nReview the final positions."
        lbl_inst = tk.Label(sidebar, text=instructions, justify=tk.LEFT, font=("Segoe UI", 10), bg="#2d2d2d", fg="#cccccc")
        lbl_inst.pack(pady=20, padx=10, fill="x")

        button_frame = tk.Frame(sidebar, bg="#2d2d2d")
        button_frame.pack(side="bottom", pady=20, padx=10, fill="x")

        back_button = ttk.Button(button_frame, text="Back", command=self.on_back)
        back_button.pack(side="left", expand=True, padx=(0, 5))

        finish_button = ttk.Button(button_frame, text="Save and Finish", command=self.on_finish)
        finish_button.pack(side="right", expand=True, padx=(5, 0))

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

            # Draw grid on the original frame
            _draw_grid_on_rectangle(drawing_frame, self.controller.final_rectangle_corners)

            # Apply zoom/pan
            M = np.array([[self.ui_state.zoom, 0, -self.ui_state.pan_offset[0] * self.ui_state.zoom],
                          [0, self.ui_state.zoom, -self.ui_state.pan_offset[1] * self.ui_state.zoom]])
            view_frame = cv2.warpAffine(drawing_frame, M, (self.ui_state.frame_width, self.ui_state.frame_height))
            
            # Convert and display
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


# --- Grid Calculation functions (copied from your original file) ---
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