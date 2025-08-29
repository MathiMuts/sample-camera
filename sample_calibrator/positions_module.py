# positions_module.py

"""
This file defines the final UI screen (`SamplePositionsFrame`) for the application.

This is the most complex step. Its responsibilities are:
1.  Using the confirmed rectangle from the previous step, it performs a
    perspective transform to overlay a real-world grid (in mm) onto the video.
2.  Allows the user to left-click within the rectangle to add sample points.
3.  Converts the pixel coordinates of each click into real-world mm coordinates.
4.  Displays the list of collected points in the sidebar, allowing them to be
    re-ordered using up/down buttons.
5.  Provides a "Push" button to format the final list of coordinates into JSON
    and send it to a predefined API endpoint.
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
# IMPORTANT: Change this URL to your actual API endpoint
PUSH_ENDPOINT_URL = "https://httpbin.org/post" # A test endpoint that echoes the request

# --- Grid Configuration Constants ---
RECT_REAL_WIDTH_MM = 130
RECT_REAL_HEIGHT_MM = 120
ZOOM_THRESHOLD_FOR_MINOR_GRID = 2.0 # Show finer grid lines when zoomed in.

SHOW_MINOR_GRID = False
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
        self.hover_coords_mm = None # Store current hovered real-world coords

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.video_label = tk.Label(self, borderwidth=0, highlightthickness=0, anchor=tk.NW)
        self.video_label.grid(row=0, column=0, sticky="nsew")

        # --- Sidebar (custom implementation for this complex frame) ---
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
        
        bottom_btn_frame = tk.Frame(sidebar, bg=ui_components.BG_COLOR)
        bottom_btn_frame.pack(side="bottom", pady=20, padx=10, fill="x")
        
        # This button's text and command change dynamically ("Back" vs "Reset").
        self.btn_left_action = ttk.Button(bottom_btn_frame, text="Back", command=self.on_back)
        self.btn_left_action.pack(side="left", expand=True, padx=(0, 5))
        
        self.btn_push = ttk.Button(bottom_btn_frame, text="Push", command=self._push_data, state="disabled")
        self.btn_push.pack(side="right", expand=True, padx=(5, 0))
        
        # --- Event Bindings ---
        self.video_label.bind("<Button>", self.on_mouse_event)
        self.video_label.bind("<ButtonPress-2>", self.on_mouse_event)
        self.video_label.bind("<ButtonRelease-2>", self.on_mouse_event)
        self.video_label.bind("<B2-Motion>", self.on_mouse_event)
        self.video_label.bind("<MouseWheel>", self.on_mouse_event)
        # Add new bindings for hover and leave events
        self.video_label.bind("<Motion>", self.on_mouse_hover)
        self.video_label.bind("<Leave>", self.on_mouse_leave)


    def on_show(self):
        self._is_active = True
        self.sample_points = [] # Always start with a clean list.
        self.hover_coords_mm = None # Reset hover state
        self._update_sidebar_list()
        self._on_listbox_select()
        self._update_button_states()
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

            # --- Draw Hover Coordinate Box on the final view_frame ---
            if self.hover_coords_mm is not None:
                text = f"({self.hover_coords_mm[0]:.1f}, {self.hover_coords_mm[1]:.1f}) mm"
                font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                padding, margin = 5, 10
                (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
                view_h, view_w, _ = view_frame.shape
                
                box_x1 = view_w - text_w - padding * 2 - margin
                box_y1 = view_h - text_h - baseline - padding * 2 - margin
                box_x2 = view_w - margin
                box_y2 = view_h - margin
                text_x = box_x1 + padding
                text_y = box_y2 - padding - (baseline // 2)

                cv2.rectangle(view_frame, (box_x1, box_y1), (box_x2, box_y2), (255, 255, 255), -1) # White BG
                cv2.putText(view_frame, text, (text_x, text_y), font, scale, (0, 0, 0), thickness, cv2.LINE_AA) # Black text

            img = cv2.cvtColor(view_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img)
            self.imgtk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.config(image=self.imgtk)
        self.after(15, self.video_loop)

    def on_mouse_hover(self, event):
        """Handles mouse motion (hover) to display real-world coordinates."""
        if self.ui_state is None: return
        # Convert view coordinates (with zoom/pan) back to original camera coordinates
        cam_x = (event.x / self.ui_state.zoom) + self.ui_state.pan_offset[0]
        cam_y = (event.y / self.ui_state.zoom) + self.ui_state.pan_offset[1]
        self.hover_coords_mm = self._transform_cam_to_real((cam_x, cam_y))

    def on_mouse_leave(self, event):
        """Clears the hover coordinates when the mouse leaves the video label."""
        self.hover_coords_mm = None

    def on_mouse_event(self, event):
        if self.ui_state is None: return
        
        if event.num == 1 and event.type == tk.EventType.ButtonPress: # Left-click
            point_on_cam = ui_components.handle_view_controls(cv2.EVENT_LBUTTONDOWN, event.x, event.y, 0, self.ui_state)
            # Transform from pixel space to real-world mm space.
            point_in_real_mm = self._transform_cam_to_real(point_on_cam)
            if point_in_real_mm is not None: # A point is only added if it's inside the rectangle.
                self.sample_points.append({'cam_coords': point_on_cam, 'real_coords': point_in_real_mm})
                self._update_sidebar_list()
                self._update_button_states()

        elif event.num == 3 and event.type == tk.EventType.ButtonPress: # Right-click
            point_on_cam = ui_components.handle_view_controls(cv2.EVENT_RBUTTONDOWN, event.x, event.y, 0, self.ui_state)
            if self.sample_points:
                detection_radius = 15 / self.ui_state.zoom
                distances = [np.linalg.norm(np.array(p['cam_coords']) - point_on_cam) for p in self.sample_points]
                min_dist_idx = np.argmin(distances)
                if distances[min_dist_idx] < detection_radius:
                    del self.sample_points[min_dist_idx]
                    self._update_sidebar_list()
                    self._update_button_states()
        
        else:
            event_map = {tk.EventType.ButtonPress: cv2.EVENT_MBUTTONDOWN, tk.EventType.ButtonRelease: cv2.EVENT_MBUTTONUP, tk.EventType.Motion: cv2.EVENT_MOUSEMOVE, tk.EventType.MouseWheel: cv2.EVENT_MOUSEWHEEL}
            cv2_event = event_map.get(event.type)
            if cv2_event is not None:
                flags = event.delta if cv2_event == cv2.EVENT_MOUSEWHEEL else 0
                ui_components.handle_view_controls(cv2_event, event.x, event.y, flags, self.ui_state)

    def _update_button_states(self):
        """Dynamically changes the bottom-left button and enables/disables the push button."""
        has_points = len(self.sample_points) > 0
        if has_points:
            self.btn_left_action.config(text="Reset", command=self._reset_points)
            self.btn_push.config(state="normal")
        else:
            self.btn_left_action.config(text="Back", command=self.on_back)
            self.btn_push.config(state="disabled")

    def _push_data(self):
        if not self.sample_points:
            messagebox.showwarning("No Data", "There are no sample points to push.")
            return

        # Format the data into the required JSON structure.
        coordinates = [
            {"x": round(float(p['real_coords'][0]), 2), "y": round(float(p['real_coords'][1]), 2)}
            for p in self.sample_points
        ]
        payload = {"coordinates": coordinates}

        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(PUSH_ENDPOINT_URL, data=json.dumps(payload), headers=headers, timeout=10)
            response.raise_for_status() # Raises an exception for 4xx or 5xx status codes.
            messagebox.showinfo("Success", f"Data successfully pushed.\nStatus Code: {response.status_code}")
            print(f"Push successful. Response: {response.json()}")
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Push Failed", f"An error occurred while sending data:\n{e}")
            print(f"Push failed: {e}")

    def _transform_cam_to_real(self, point_on_cam):
        corners = self.controller.final_rectangle_corners
        if corners is None or len(corners) != 4: return None
        src_pts = _order_points(corners)
        # Define the destination as a perfect, un-rotated rectangle with real-world dimensions.
        dst_w, dst_h = RECT_REAL_WIDTH_MM * 10, RECT_REAL_HEIGHT_MM * 10
        dst_pts = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype="float32")
        # Get the matrix that transforms points from the camera's perspective to the ideal rectangle.
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        point_to_transform = np.array([[point_on_cam]], dtype="float32")
        transformed_point = cv2.perspectiveTransform(point_to_transform, M)[0][0]
        # Check if the transformed point is within the bounds of the real-world rectangle.
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
            self._update_sidebar_list()
            self.listbox.selection_set(idx - 1)
            self.listbox.activate(idx - 1)
            self._on_listbox_select()

    def _move_item_down(self):
        selected_indices = self.listbox.curselection()
        if not selected_indices: return
        idx = selected_indices[0]
        if idx < len(self.sample_points) - 1:
            self.sample_points[idx], self.sample_points[idx+1] = self.sample_points[idx+1], self.sample_points[idx]
            self._update_sidebar_list()
            self.listbox.selection_set(idx + 1)
            self.listbox.activate(idx + 1)
            self._on_listbox_select()
    
    def _reset_points(self):
        if not self.sample_points: return
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to remove all sample points?"):
            self.sample_points.clear()
            self._update_sidebar_list()
            self._on_listbox_select()
            self._update_button_states()
    
    def on_back(self):
        self.on_hide()
        self.controller.sample_positions_complete('back')

def _order_points(pts):
    """Sorts 4 points into a consistent order: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)] # TL has smallest sum, BR has largest.
    diff = np.diff(pts, axis=1)
    rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)] # TR has smallest diff, BL has largest.
    return rect

def _draw_dynamic_grid(frame, corners, ui_state, sample_points):
    if corners is None or len(corners) != 4 or ui_state is None: return
    src_pts = _order_points(corners)
    dst_w, dst_h = RECT_REAL_WIDTH_MM * 10, RECT_REAL_HEIGHT_MM * 10
    dst_pts = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype="float32")
    # We need the inverse transform to map points from the ideal grid onto the warped camera view.
    M = cv2.getPerspectiveTransform(dst_pts, src_pts)
    all_endpoints_major, all_endpoints_minor = [], []
    major_step = 10 * 10 # 10mm
    for x in range(major_step, dst_w, major_step): all_endpoints_major.extend([(x, 0), (x, dst_h - 1)])
    for y in range(major_step, dst_h, major_step): all_endpoints_major.extend([(0, y), (dst_w - 1, y)])
    if SHOW_MINOR_GRID and ui_state.zoom > ZOOM_THRESHOLD_FOR_MINOR_GRID:
        minor_step = 5 * 10 # 5mm
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
        cv2.circle(frame, (px, py), 3, COLOR_SAMPLE_POINT, -1, cv2.LINE_AA)
        cv2.circle(frame, (px, py), 3, (255,255,255), 1, cv2.LINE_AA)
        text_pos = (px + 8, py + 5)
        cv2.putText(frame, label, (text_pos[0]+1, text_pos[1]+1), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,0), 1, cv2.LINE_AA) # Shadow
        cv2.putText(frame, label, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_SAMPLE_TEXT, 1, cv2.LINE_AA)
    cv2.drawContours(frame, [np.int32(corners)], 0, COLOR_RECTANGLE_BORDER, 2, cv2.LINE_AA)