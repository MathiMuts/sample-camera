# sample_calibrator/sample_positions_module.py

import tkinter as tk
from tkinter import ttk, font, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import ui_components

# --- Grid Configuration Constants ---
RECT_REAL_WIDTH_MM = 130
RECT_REAL_HEIGHT_MM = 120
ZOOM_THRESHOLD_FOR_MINOR_GRID = 2.0

# --- Drawing Style Constants ---
COLOR_RECTANGLE_BORDER = (0, 255, 0)
GRID_COLOR_MAJOR = (128, 128, 128)
GRID_COLOR_MINOR = (80, 80, 80)
GRID_THICKNESS_MAJOR = 1
GRID_THICKNESS_MINOR = 1
COLOR_SAMPLE_POINT = (240, 180, 0)
COLOR_SAMPLE_TEXT = (255, 255, 255)

class SamplePositionsFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        self.controller = controller
        self.cap = cap
        self.ui_state = None
        self._is_active = False
        self.sample_points = []

        # --- Layout ---
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Widgets ---
        self.video_label = tk.Label(self, borderwidth=0, highlightthickness=0, anchor=tk.NW)
        self.video_label.grid(row=0, column=0, sticky="nsew")

        # --- Sidebar ---
        sidebar = tk.Frame(self, width=ui_components.SIDEBAR_WIDTH, bg=ui_components.BG_COLOR)
        sidebar.pack_propagate(False)
        sidebar.grid(row=0, column=1, sticky="ns")
        
        lbl_title = tk.Label(sidebar, text="Step 3: Collect Samples", font=ui_components.FONT_TITLE, bg=ui_components.BG_COLOR, fg=ui_components.FG_COLOR_LIGHT)
        lbl_title.pack(pady=10, padx=10, anchor="w")
        instructions = "Left-click to add a sample point.\nRight-click to remove the nearest point.\nUse the buttons to reorder."
        lbl_inst = tk.Label(sidebar, text=instructions, justify=tk.LEFT, wraplength=ui_components.SIDEBAR_WIDTH-20, font=ui_components.FONT_BODY, bg=ui_components.BG_COLOR, fg=ui_components.FG_COLOR_MUTED)
        lbl_inst.pack(pady=10, padx=10, anchor="w", fill="x")

        list_frame = tk.Frame(sidebar, bg=ui_components.BG_COLOR)
        list_frame.pack(pady=5, padx=10, fill="both", expand=True)

        self.listbox = tk.Listbox(list_frame, bg="#3d3d3d", fg="white", selectbackground="#0078d7", borderwidth=0, highlightthickness=0, font=("Consolas", 10))
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind('<<ListboxSelect>>', self._on_listbox_select)

        btn_frame = tk.Frame(list_frame, bg=ui_components.BG_COLOR)
        btn_frame.pack(side="right", fill="y", padx=(5,0))
        
        self.btn_up = ttk.Button(btn_frame, text="▲", command=self._move_item_up, width=3, state="disabled")
        self.btn_up.pack(pady=(0, 2))
        self.btn_down = ttk.Button(btn_frame, text="▼", command=self._move_item_down, width=3, state="disabled")
        self.btn_down.pack()
        
        # --- Bottom navigation buttons ---
        bottom_btn_frame = tk.Frame(sidebar, bg=ui_components.BG_COLOR)
        bottom_btn_frame.pack(side="bottom", pady=20, padx=10, fill="x")
        
        # MODIFIED: "Back" button is now the only one on the left
        ttk.Button(bottom_btn_frame, text="Back", command=self.on_back).pack(side="left", expand=True, padx=(0, 5))
        
        # MODIFIED: Changed the button to a simple "Reset"
        self.btn_reset = ttk.Button(bottom_btn_frame, text="Reset", command=self._reset_points, state="disabled")
        self.btn_reset.pack(side="right", expand=True, padx=(5, 0))
        
        self.video_label.bind("<Button>", self.on_mouse_event)
        self.video_label.bind("<ButtonPress-2>", self.on_mouse_event)
        self.video_label.bind("<ButtonRelease-2>", self.on_mouse_event)
        self.video_label.bind("<B2-Motion>", self.on_mouse_event)
        self.video_label.bind("<MouseWheel>", self.on_mouse_event)

    def on_show(self):
        self._is_active = True
        self.sample_points = []
        self._update_sidebar_list()
        self._on_listbox_select()
        self.btn_reset.config(state="disabled") # Ensure reset is disabled on show
        ret, frame = self.cap.read()
        if ret:
            frame_h, frame_w, _ = cv2.flip(frame, -1).shape
            self.ui_state = ui_components.BaseUIState(frame_w, frame_h)
        self.video_loop()

    def on_hide(self):
        self._is_active = False

    def video_loop(self):
        if not self._is_active or self.ui_state is None: return
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, -1)
            drawing_frame = frame.copy()
            _draw_dynamic_grid(drawing_frame, self.controller.final_rectangle_corners, self.ui_state, self.sample_points)
            M = np.array([[self.ui_state.zoom, 0, -self.ui_state.pan_offset[0] * self.ui_state.zoom],
                          [0, self.ui_state.zoom, -self.ui_state.pan_offset[1] * self.ui_state.zoom]])
            view_frame = cv2.warpAffine(drawing_frame, M, (self.ui_state.frame_width, self.ui_state.frame_height))
            img = cv2.cvtColor(view_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img)
            self.imgtk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.config(image=self.imgtk)
        self.after(15, self.video_loop)

    def on_mouse_event(self, event):
        if self.ui_state is None: return
        
        if event.num == 1 and event.type == tk.EventType.ButtonPress:
            point_on_cam = ui_components.handle_view_controls(cv2.EVENT_LBUTTONDOWN, event.x, event.y, 0, self.ui_state)
            point_in_real_mm = self._transform_cam_to_real(point_on_cam)
            if point_in_real_mm is not None:
                self.sample_points.append({'cam_coords': point_on_cam, 'real_coords': point_in_real_mm})
                self._update_sidebar_list()
                self.btn_reset.config(state="normal")

        elif event.num == 3 and event.type == tk.EventType.ButtonPress:
            point_on_cam = ui_components.handle_view_controls(cv2.EVENT_RBUTTONDOWN, event.x, event.y, 0, self.ui_state)
            if self.sample_points:
                detection_radius = 15 / self.ui_state.zoom
                distances = [np.linalg.norm(np.array(p['cam_coords']) - point_on_cam) for p in self.sample_points]
                min_dist_idx = np.argmin(distances)
                if distances[min_dist_idx] < detection_radius:
                    del self.sample_points[min_dist_idx]
                    self._update_sidebar_list()
                    if not self.sample_points:
                        self.btn_reset.config(state="disabled")
        
        else:
            event_map = {tk.EventType.ButtonPress: cv2.EVENT_MBUTTONDOWN, tk.EventType.ButtonRelease: cv2.EVENT_MBUTTONUP, tk.EventType.Motion: cv2.EVENT_MOUSEMOVE, tk.EventType.MouseWheel: cv2.EVENT_MOUSEWHEEL}
            cv2_event = event_map.get(event.type)
            if cv2_event is not None:
                flags = event.delta if cv2_event == cv2.EVENT_MOUSEWHEEL else 0
                ui_components.handle_view_controls(cv2_event, event.x, event.y, flags, self.ui_state)

    def _transform_cam_to_real(self, point_on_cam):
        corners = self.controller.final_rectangle_corners
        if corners is None or len(corners) != 4: return None
        src_pts = _order_points(corners)
        dst_w, dst_h = RECT_REAL_WIDTH_MM * 10, RECT_REAL_HEIGHT_MM * 10
        dst_pts = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype="float32")
        M_inv = cv2.getPerspectiveTransform(src_pts, dst_pts)
        point_to_transform = np.array([[point_on_cam]], dtype="float32")
        transformed_point = cv2.perspectiveTransform(point_to_transform, M_inv)[0][0]
        if 0 <= transformed_point[0] < dst_w and 0 <= transformed_point[1] < dst_h:
            return (transformed_point[0] / 10.0, transformed_point[1] / 10.0)
        return None

    def _update_sidebar_list(self):
        self.listbox.delete(0, tk.END)
        for i, point in enumerate(self.sample_points):
            rx, ry = point['real_coords']
            self.listbox.insert(tk.END, f"{i+1:<3} ({rx:6.1f}, {ry:6.1f}) mm")

    def _on_listbox_select(self, event=None):
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            self.btn_up.config(state="disabled")
            self.btn_down.config(state="disabled")
            return
        idx = selected_indices[0]
        self.btn_up.config(state="normal" if idx > 0 else "disabled")
        self.btn_down.config(state="normal" if idx < len(self.sample_points) - 1 else "disabled")

    def _move_item_up(self):
        selected_indices = self.listbox.curselection()
        if not selected_indices: return
        idx = selected_indices[0]
        if idx > 0:
            self.sample_points[idx], self.sample_points[idx-1] = self.sample_points[idx-1], self.sample_points[idx]
            new_idx = idx - 1
            self._update_sidebar_list()
            self.listbox.selection_set(new_idx)
            self.listbox.activate(new_idx)
            self.listbox.focus_set()
            self._on_listbox_select()

    def _move_item_down(self):
        selected_indices = self.listbox.curselection()
        if not selected_indices: return
        idx = selected_indices[0]
        if idx < len(self.sample_points) - 1:
            self.sample_points[idx], self.sample_points[idx+1] = self.sample_points[idx+1], self.sample_points[idx]
            new_idx = idx + 1
            self._update_sidebar_list()
            self.listbox.selection_set(new_idx)
            self.listbox.activate(new_idx)
            self.listbox.focus_set()
            self._on_listbox_select()
    
    # NEW: Simplified reset method
    def _reset_points(self):
        """Clears all collected sample points after confirmation."""
        if not self.sample_points:
            return
        
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to remove all sample points?"):
            self.sample_points.clear()
            self._update_sidebar_list()
            self._on_listbox_select() # Disables up/down buttons
            self.btn_reset.config(state="disabled") # Disables reset button
    
    # MODIFIED: This is now the only way to leave this screen, besides closing the app
    def on_back(self):
        # We can also print the data here if desired, or just discard it.
        # For now, we discard the points when going back.
        print("Returning to placement confirmation. Sample points cleared.")
        self.on_hide()
        self.controller.sample_positions_complete('back')

# --- Helper functions remain the same ---
def _order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)]
    return rect

def _draw_dynamic_grid(frame, corners, ui_state, sample_points):
    if corners is None or len(corners) != 4 or ui_state is None: return
    src_pts = _order_points(corners)
    dst_w, dst_h = RECT_REAL_WIDTH_MM * 10, RECT_REAL_HEIGHT_MM * 10
    dst_pts = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(dst_pts, src_pts)
    all_endpoints_major, all_endpoints_minor = [], []
    major_step = 10 * 10
    for x in range(major_step, dst_w, major_step): all_endpoints_major.extend([(x, 0), (x, dst_h - 1)])
    for y in range(major_step, dst_h, major_step): all_endpoints_major.extend([(0, y), (dst_w - 1, y)])
    if ui_state.zoom > ZOOM_THRESHOLD_FOR_MINOR_GRID:
        minor_step = 5 * 10
        for x in range(minor_step, dst_w, minor_step):
            if x % major_step != 0: all_endpoints_minor.extend([(x, 0), (x, dst_h - 1)])
        for y in range(minor_step, dst_h, minor_step):
            if y % major_step != 0: all_endpoints_minor.extend([(0, y), (dst_w - 1, y)])
    for endpoints, color, thickness in [(all_endpoints_minor, GRID_COLOR_MINOR, GRID_THICKNESS_MINOR), (all_endpoints_major, GRID_COLOR_MAJOR, GRID_THICKNESS_MAJOR)]:
        if not endpoints: continue
        pts_to_transform = np.array([endpoints], dtype="float32")
        transformed_pts = cv2.perspectiveTransform(pts_to_transform, M)[0]
        for i in range(0, len(transformed_pts), 2):
            p1, p2 = tuple(np.int32(transformed_pts[i])), tuple(np.int32(transformed_pts[i+1]))
            cv2.line(frame, p1, p2, color, thickness, cv2.LINE_AA)
    for i, point in enumerate(sample_points):
        px, py = map(int, point['cam_coords'])
        label = str(i + 1)
        cv2.circle(frame, (px, py), 2, COLOR_SAMPLE_POINT, -1, cv2.LINE_AA)
        cv2.circle(frame, (px, py), 2, (255,255,255), 1, cv2.LINE_AA)
        text_pos = (px + 8, py + 5)
        cv2.putText(frame, label, (text_pos[0]+1, text_pos[1]+1), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,0), 1, cv2.LINE_AA)
        cv2.putText(frame, label, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_SAMPLE_TEXT, 1, cv2.LINE_AA)
    cv2.drawContours(frame, [np.int32(corners)], 0, COLOR_RECTANGLE_BORDER, 2, cv2.LINE_AA)