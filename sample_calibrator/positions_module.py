# positions_module.py

"""
This file defines the final UI screen (`SamplePositionsFrame`) for the application.

This is the most complex step. Its responsibilities are:
1.  Using the confirmed rectangle from the previous step, it performs a
    perspective transform to overlay a real-world grid (in mm) onto the video.
2.  Allows the user to left-click within the rectangle to add sample points.
3.  Converts the pixel coordinates of each click into real-world mm coordinates.
4.  Displays collected points in a table with editable "File" and "Sample ID" columns.
5.  Provides an input for a "Request Name".
6.  Provides a "Push" button to format the final data into JSON and send it to
    a predefined API endpoint.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
from . import ui_components
import requests
import json

# --- API Configuration ---
PUSH_ENDPOINT_URL = "https://httpbin.org/post"

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
TREEVIEW_FONT = ("Consolas", 10)

class SamplePositionsFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        self.controller = controller
        self.cap = cap
        self.ui_state = None
        self._is_active = False
        self.sample_points = []
        self.hover_coords_mm = None
        # --- Inline Edit State ---
        self.edit_entry = None
        self.edit_item_id = None # Treeview item ID (e.g., I001)
        self.edit_data_idx = None  # Index in the self.sample_points list
        self.edit_data_key = None  # Key being edited ('file' or 'sample_id')

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.video_label = tk.Label(self, borderwidth=0, highlightthickness=0, anchor=tk.NW)
        self.video_label.grid(row=0, column=0, sticky="nsew")

        # --- Sidebar ---
        sidebar = tk.Frame(self, width=ui_components.SIDEBAR_WIDTH, bg=ui_components.BG_COLOR)
        sidebar.pack_propagate(False)
        sidebar.grid(row=0, column=1, sticky="ns")
        
        lbl_title = tk.Label(sidebar, text="Step 3: Collect Samples", font=ui_components.FONT_TITLE, bg=ui_components.BG_COLOR, fg=ui_components.FG_COLOR_LIGHT)
        lbl_title.pack(pady=10, padx=10, anchor="w")
        instructions = "Left-click to add a point.\nRight-click to remove nearest.\nDouble-click a File or Sample ID to edit."
        lbl_inst = tk.Label(sidebar, text=instructions, justify=tk.LEFT, wraplength=ui_components.SIDEBAR_WIDTH-20, font=ui_components.FONT_BODY, bg=ui_components.BG_COLOR, fg=ui_components.FG_COLOR_MUTED)
        lbl_inst.pack(pady=10, padx=10, anchor="w", fill="x")

        # --- Request Name Input ---
        req_frame = tk.Frame(sidebar, bg=ui_components.BG_COLOR)
        req_frame.pack(pady=(10, 5), padx=10, fill="x")
        lbl_req = tk.Label(req_frame, text="Request Name:", font=ui_components.FONT_BODY, bg=ui_components.BG_COLOR, fg=ui_components.FG_COLOR_LIGHT)
        lbl_req.pack(side="left", padx=(0, 5))
        self.request_name_var = tk.StringVar()
        entry_req = ttk.Entry(req_frame, textvariable=self.request_name_var)
        entry_req.pack(side="left", fill="x", expand=True)

        # --- Sample Table (Treeview) ---
        table_frame = tk.Frame(sidebar, bg=ui_components.BG_COLOR)
        table_frame.pack(pady=5, padx=10, fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#3d3d3d", foreground="white", fieldbackground="#3d3d3d", borderwidth=0, font=TREEVIEW_FONT, rowheight=20)
        style.map('Treeview', background=[('selected', '#0078d7')])
        style.configure("Treeview.Heading", background=ui_components.BG_COLOR, foreground="white", relief="flat", font=ui_components.FONT_BODY)
        style.map("Treeview.Heading", background=[('active', '#3c3c3c')])

        self.tree = ttk.Treeview(table_frame, columns=("file", "sample_id", "coords"), show='headings')
        self.tree.heading("file", text="File")
        self.tree.heading("sample_id", text="Sample ID")
        self.tree.heading("coords", text="Coords (mm)")

        self.tree.column("file", width=50, anchor=tk.CENTER)
        self.tree.column("sample_id", width=90, anchor=tk.W)
        self.tree.column("coords", width=100, anchor=tk.CENTER)

        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind('<Double-1>', self._on_tree_double_click)
        
        bottom_btn_frame = tk.Frame(sidebar, bg=ui_components.BG_COLOR)
        bottom_btn_frame.pack(side="bottom", pady=20, padx=10, fill="x")
        
        self.btn_left_action = ttk.Button(bottom_btn_frame, text="Back", command=self.on_back)
        self.btn_left_action.pack(side="left", expand=True, padx=(0, 5))
        
        self.btn_push = ttk.Button(bottom_btn_frame, text="Push", command=self._push_data, state="disabled")
        self.btn_push.pack(side="right", expand=True, padx=(5, 0))
        
        # --- Event Bindings ---
        self.video_label.bind("<Button>", self.on_mouse_event)
        self.video_label.bind("<Motion>", self.on_mouse_hover)
        self.video_label.bind("<Leave>", self.on_mouse_leave)

    def on_show(self):
        self._is_active = True
        self.sample_points = []
        self.request_name_var.set("")
        self.hover_coords_mm = None
        self._update_treeview()
        self._update_button_states()
        if self.edit_entry: self._cancel_edit()
        ret, frame = self.cap.read()
        if ret:
            frame_h, frame_w, _ = cv2.flip(frame, -1).shape
            self.ui_state = ui_components.BaseUIState(frame_w, frame_h)
        self.video_loop()

    def on_hide(self): self._is_active = False

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

            if self.hover_coords_mm is not None:
                text = f"({self.hover_coords_mm[0]:.1f},{self.hover_coords_mm[1]:.1f}) mm"
                font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
                padding, margin = 5, 10
                view_h, view_w, _ = view_frame.shape
                box_x1 = view_w - text_w - padding * 2 - margin
                box_y1 = view_h - text_h - baseline - padding * 2 - margin
                box_x2 = view_w - margin
                box_y2 = view_h - margin
                cv2.rectangle(view_frame, (box_x1, box_y1), (box_x2, box_y2), (255, 255, 255), -1)
                cv2.putText(view_frame, text, (box_x1 + padding, box_y2 - padding - (baseline // 2)), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)

            img = cv2.cvtColor(view_frame, cv2.COLOR_BGR2RGB)
            self.imgtk = ImageTk.PhotoImage(image=Image.fromarray(img))
            self.video_label.config(image=self.imgtk)
        self.after(15, self.video_loop)

    def on_mouse_hover(self, event):
        if self.ui_state is None: return
        cam_x = (event.x / self.ui_state.zoom) + self.ui_state.pan_offset[0]
        cam_y = (event.y / self.ui_state.zoom) + self.ui_state.pan_offset[1]
        self.hover_coords_mm = self._transform_cam_to_real((cam_x, cam_y))

    def on_mouse_leave(self, event): self.hover_coords_mm = None

    def on_mouse_event(self, event):
        if self.ui_state is None: return
        if self.edit_entry: self._commit_edit()

        tk_to_cv2_map = {
            (tk.EventType.ButtonPress, 2): cv2.EVENT_MBUTTONDOWN,
            (tk.EventType.ButtonRelease, 2): cv2.EVENT_MBUTTONUP,
            (tk.EventType.Motion, 2): cv2.EVENT_MOUSEMOVE,
            (tk.EventType.MouseWheel, 0): cv2.EVENT_MOUSEWHEEL
        }

        if event.type == tk.EventType.ButtonPress:
            if event.num == 1: # Left-click to add point
                point_on_cam = ui_components.handle_view_controls(cv2.EVENT_LBUTTONDOWN, event.x, event.y, 0, self.ui_state)
                point_in_real_mm = self._transform_cam_to_real(point_on_cam)
                if point_in_real_mm is not None:
                    new_file_id = str(len(self.sample_points) + 1)
                    self.sample_points.append({'file': new_file_id, 'sample_id': '', 'cam_coords': point_on_cam, 'real_coords': point_in_real_mm})
                    self._update_treeview()
                    self._update_button_states()
            elif event.num == 3: # Right-click to delete point
                point_on_cam = ui_components.handle_view_controls(cv2.EVENT_RBUTTONDOWN, event.x, event.y, 0, self.ui_state)
                if self.sample_points:
                    detection_radius = 15 / self.ui_state.zoom
                    distances = [np.linalg.norm(np.array(p['cam_coords']) - point_on_cam) for p in self.sample_points]
                    min_dist_idx = np.argmin(distances)
                    if distances[min_dist_idx] < detection_radius:
                        del self.sample_points[min_dist_idx]
                        self._renumber_files()
                        self._update_treeview()
                        self._update_button_states()
        
        btn_num = event.num if event.type != tk.EventType.MouseWheel else 0
        cv2_event = tk_to_cv2_map.get((event.type, btn_num))
        if cv2_event:
            flags = event.delta if cv2_event == cv2.EVENT_MOUSEWHEEL else 0
            ui_components.handle_view_controls(cv2_event, event.x, event.y, flags, self.ui_state)

    def _update_button_states(self):
        has_points = len(self.sample_points) > 0
        if has_points:
            self.btn_left_action.config(text="Reset", command=self._reset_points)
            self.btn_push.config(state="normal")
        else:
            self.btn_left_action.config(text="Back", command=self.on_back)
            self.btn_push.config(state="disabled")

    def _push_data(self):
        if self.edit_entry: self._commit_edit()
        request_name = self.request_name_var.get().strip()
        if not request_name:
            messagebox.showwarning("Missing Info", "Please enter a Request Name.")
            return
        if not self.sample_points:
            messagebox.showwarning("No Data", "There are no sample points to push.")
            return

        samples = [{"file": p['file'], "sample_id": p['sample_id'], "x": round(float(p['real_coords'][0]), 2), "y": round(float(p['real_coords'][1]), 2)} for p in self.sample_points]
        payload = {"request_name": request_name, "samples": samples}

        print("\n--- Pushing JSON Payload ---")
        print(json.dumps(payload, indent=4))
        print("--------------------------\n")

        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(PUSH_ENDPOINT_URL, data=json.dumps(payload), headers=headers, timeout=10)
            response.raise_for_status()
            messagebox.showinfo("Success", f"Data successfully pushed.\nStatus Code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Push Failed", f"An error occurred while sending data:\n{e}")

    def _transform_cam_to_real(self, point_on_cam):
        corners = self.controller.final_rectangle_corners
        if corners is None or len(corners) != 4: return None
        src_pts = _order_points(corners)
        dst_w, dst_h = RECT_REAL_WIDTH_MM * 10, RECT_REAL_HEIGHT_MM * 10
        dst_pts = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype="float32")
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        transformed_point = cv2.perspectiveTransform(np.array([[point_on_cam]], dtype="float32"), M)[0][0]
        if 0 <= transformed_point[0] < dst_w and 0 <= transformed_point[1] < dst_h:
            return (transformed_point[0] / 10.0, transformed_point[1] / 10.0)
        return None
    
    def _renumber_files(self):
        for i, point in enumerate(self.sample_points):
            point['file'] = str(i + 1)

    def _update_treeview(self):
        self.tree.delete(*self.tree.get_children())
        for point in self.sample_points:
            rx, ry = point['real_coords']
            coords_str = f"({rx:.1f},{ry:.1f})"
            self.tree.insert('', 'end', values=(point['file'], point['sample_id'], coords_str))

    def _on_tree_double_click(self, event=None):
        if self.edit_entry: self._commit_edit()
        
        column_map = {"#1": "file", "#2": "sample_id"}
        column_id = self.tree.identify_column(event.x)
        
        if self.tree.identify_region(event.x, event.y) != "cell" or column_id not in column_map:
            return

        self.edit_item_id = self.tree.identify_row(event.y)
        if not self.edit_item_id: return

        # --- BUG FIX: Use the Treeview index to find the data item ---
        # This is robust and prevents order scrambling because the visual index
        # in the tree always matches the data index in self.sample_points.
        try:
            self.edit_data_idx = self.tree.index(self.edit_item_id)
        except ValueError:
            # This can happen in rare race conditions; safely ignore.
            return
            
        self.edit_data_key = column_map[column_id]
        
        # Proceed with creating the edit box
        x, y, w, h = self.tree.bbox(self.edit_item_id, column=column_id)
        self.edit_entry = ttk.Entry(self.tree, font=TREEVIEW_FONT)
        self.edit_entry.place(x=x, y=y, width=w, height=h)
        
        current_value = self.sample_points[self.edit_data_idx][self.edit_data_key]
        self.edit_entry.insert(0, current_value)
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus_set()
    
        self.edit_entry.bind("<Return>", self._commit_edit)
        self.edit_entry.bind("<FocusOut>", self._commit_edit)
        self.edit_entry.bind("<Escape>", self._cancel_edit)

    def _commit_edit(self, event=None):
        if not self.edit_entry: return
        new_value = self.edit_entry.get().strip()
        if self.edit_data_idx is not None and self.edit_data_key:
            # Make sure index is still valid before writing
            if self.edit_data_idx < len(self.sample_points):
                self.sample_points[self.edit_data_idx][self.edit_data_key] = new_value
        
        self._cancel_edit()
        self._update_treeview()

    def _cancel_edit(self, event=None):
        if self.edit_entry: self.edit_entry.destroy()
        self.edit_entry = None
        self.edit_item_id = None
        self.edit_data_idx = None
        self.edit_data_key = None
    
    def _reset_points(self):
        if self.edit_entry: self._cancel_edit()
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to remove all sample points?"):
            self.sample_points.clear()
            self._update_treeview()
            self._update_button_states()
    
    def on_back(self):
        if self.edit_entry: self._cancel_edit()
        self.on_hide()
        self.controller.sample_positions_complete('back')

def _order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s, diff = pts.sum(axis=1), np.diff(pts, axis=1)
    rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]
    rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)]
    return rect

def _draw_dynamic_grid(frame, corners, ui_state, sample_points):
    if corners is None or len(corners) != 4 or ui_state is None: return
    for point in sample_points:
        px, py = map(int, point['cam_coords'])
        label = str(point['file'])
        cv2.circle(frame, (px, py), 3, COLOR_SAMPLE_POINT, -1, cv2.LINE_AA)
        cv2.circle(frame, (px, py), 3, (255,255,255), 1, cv2.LINE_AA)
        text_pos = (px + 8, py + 5)
        cv2.putText(frame, label, (text_pos[0]+1, text_pos[1]+1), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,0), 1, cv2.LINE_AA)
        cv2.putText(frame, label, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_SAMPLE_TEXT, 1, cv2.LINE_AA)
    cv2.drawContours(frame, [np.int32(corners)], 0, COLOR_RECTANGLE_BORDER, 2, cv2.LINE_AA)