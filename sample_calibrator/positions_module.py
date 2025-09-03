import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
from . import ui_components
import os
import csv
import io

# --- File Path Configuration ---
IMAGES_PATH = "/mnt/winbe_wasp_rbs_images"
RECEPIES_PATH = "/mnt/winbe_wasp_rbs_recipes"

# --- CSV Generation Constants ---
JOB_TYPE = "rbs"
SAMPLE_TYPE = "rbs_random"
PHI = 15
ZETA = ""
DET = 0.15
THETA = 170
RUN_NUMBER = 11

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
TREEVIEW_FONT = ("Consolas", 14)

class SamplePositionsFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        self.controller = controller
        self.cap = cap
        self.ui_state = None
        self._is_active = False
        self.sample_points = []
        self.hover_coords_mm = None
        self.last_rendered_frame = None

        self.display_scale = 1.0
        self.pad_x = 0
        self.pad_y = 0

        self.edit_entry = None
        self.edit_item_id = None
        self.edit_data_idx = None
        self.edit_data_key = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.video_label = tk.Label(self, borderwidth=0, highlightthickness=0, bg="black")
        self.video_label.grid(row=0, column=0, sticky="nsew")

        sidebar = tk.Frame(self, width=ui_components.SIDEBAR_WIDTH, bg=ui_components.BG_COLOR)
        sidebar.pack_propagate(False)
        sidebar.grid(row=0, column=1, sticky="ns")
        
        lbl_title = tk.Label(sidebar, text="Step 3: Collect Samples", font=ui_components.FONT_TITLE, bg=ui_components.BG_COLOR, fg=ui_components.FG_COLOR_LIGHT)
        lbl_title.pack(pady=10, padx=10, anchor="w")
        instructions = "Left-click to add a point.\nRight-click to remove nearest.\nDouble-click a File or Sample ID to edit."
        lbl_inst = tk.Label(sidebar, text=instructions, justify=tk.LEFT, wraplength=ui_components.SIDEBAR_WIDTH-20, font=ui_components.FONT_BODY, bg=ui_components.BG_COLOR, fg=ui_components.FG_COLOR_MUTED)
        lbl_inst.pack(pady=10, padx=10, anchor="w", fill="x")

        req_frame = tk.Frame(sidebar, bg=ui_components.BG_COLOR)
        req_frame.pack(pady=(10, 5), padx=10, fill="x")
        lbl_req = tk.Label(req_frame, text="Request Name:", font=ui_components.FONT_BODY, bg=ui_components.BG_COLOR, fg=ui_components.FG_COLOR_LIGHT)
        lbl_req.pack(side="left", padx=(0, 5))
        self.request_name_var = tk.StringVar()
        entry_req = ttk.Entry(req_frame, textvariable=self.request_name_var)
        entry_req.pack(side="left", fill="x", expand=True)

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
        
        self.btn_save = ttk.Button(bottom_btn_frame, text="Save", command=self._push_data, state="disabled")
        self.btn_save.pack(side="right", expand=True, padx=(5, 0))
        
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
            frame_h, frame_w, _ = frame.shape
            self.ui_state = ui_components.BaseUIState(frame_w, frame_h)
        self.video_loop()

    def on_hide(self): self._is_active = False

    def video_loop(self):
        if not self._is_active or self.ui_state is None: return

        label_w = self.video_label.winfo_width()
        label_h = self.video_label.winfo_height()

        if label_w < 10 or label_h < 10:
            self.after(15, self.video_loop)
            return

        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, -1)
            
            cam_h, cam_w, _ = frame.shape
            drawing_frame = frame.copy()
            _draw_dynamic_grid(drawing_frame, self.controller.final_rectangle_corners, self.ui_state, self.sample_points)
            
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

            if self.hover_coords_mm is not None:
                text = f"({self.hover_coords_mm[0]:.1f},{self.hover_coords_mm[1]:.1f}) mm"
                font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
                padding, margin = 5, 10
                box_x1 = label_w - text_w - padding * 2 - margin
                box_y1 = label_h - text_h - baseline - padding * 2 - margin
                box_x2 = label_w - margin
                box_y2 = label_h - margin
                cv2.rectangle(canvas, (box_x1, box_y1), (box_x2, box_y2), (255, 255, 255), -1)
                cv2.putText(canvas, text, (box_x1 + padding, box_y2 - padding - (baseline // 2)), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)
            
            self.last_rendered_frame = canvas.copy()
            img = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            self.imgtk = ImageTk.PhotoImage(image=Image.fromarray(img))
            self.video_label.config(image=self.imgtk)
        self.after(15, self.video_loop)

    def _view_to_cam_coords(self, x, y):
        if self.display_scale == 0: return 0, 0
        cam_x = (x - self.pad_x) / self.display_scale
        cam_y = (y - self.pad_y) / self.display_scale
        return cam_x, cam_y

    def on_mouse_hover(self, event):
        if self.ui_state is None: return
        cam_x, cam_y = self._view_to_cam_coords(event.x, event.y)
        point_on_original_frame = self.ui_state.pan_offset + np.array([cam_x, cam_y]) / self.ui_state.zoom
        self.hover_coords_mm = self._transform_cam_to_real(point_on_original_frame)

    def on_mouse_leave(self, event): self.hover_coords_mm = None

    def on_mouse_event(self, event):
        if self.ui_state is None: return
        if self.edit_entry: self._commit_edit()

        cam_x, cam_y = self._view_to_cam_coords(event.x, event.y)
        cam_x = np.clip(cam_x, 0, self.ui_state.frame_width - 1)
        cam_y = np.clip(cam_y, 0, self.ui_state.frame_height - 1)

        tk_to_cv2_map = {
            (tk.EventType.ButtonPress, 2): cv2.EVENT_MBUTTONDOWN,
            (tk.EventType.ButtonRelease, 2): cv2.EVENT_MBUTTONUP,
            (tk.EventType.Motion, 2): cv2.EVENT_MOUSEMOVE,
            (tk.EventType.MouseWheel, 0): cv2.EVENT_MOUSEWHEEL
        }

        if event.type == tk.EventType.ButtonPress:
            if event.num == 1:
                point_on_cam = ui_components.handle_view_controls(cv2.EVENT_LBUTTONDOWN, cam_x, cam_y, 0, self.ui_state)
                point_in_real_mm = self._transform_cam_to_real(point_on_cam)
                if point_in_real_mm is not None:
                    new_file_id = str(len(self.sample_points) + 1).zfill(2)
                    self.sample_points.append({'file': new_file_id, 'sample_id': '', 'cam_coords': point_on_cam, 'real_coords': point_in_real_mm})
                    self._update_treeview()
                    self._update_button_states()
            elif event.num == 3:
                point_on_cam = ui_components.handle_view_controls(cv2.EVENT_RBUTTONDOWN, cam_x, cam_y, 0, self.ui_state)
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
            ui_components.handle_view_controls(cv2_event, cam_x, cam_y, flags, self.ui_state)

    def _update_button_states(self):
        has_points = len(self.sample_points) > 0
        if has_points:
            self.btn_left_action.config(text="Reset", command=self._reset_points)
            self.btn_save.config(state="normal")
        else:
            self.btn_left_action.config(text="Back", command=self.on_back)
            self.btn_save.config(state="disabled")

    def _push_data(self):
        if self.edit_entry: self._commit_edit()
        request_name = self.request_name_var.get().strip()
        if not request_name:
            messagebox.showwarning("Missing Info", "Please enter a Request Name.")
            return
        if not self.sample_points:
            messagebox.showwarning("No Data", "There are no sample points to save.")
            return
        if self.last_rendered_frame is None:
            messagebox.showerror("Save Failed", "Could not capture a screenshot. Please try again.")
            return

        csv_output = io.StringIO()
        writer = csv.writer(csv_output)
        writer.writerow(['name', 'job_type'] + [''] * 8)
        writer.writerow([request_name, JOB_TYPE] + [''] * 8)
        writer.writerow([''] * 10)
        writer.writerow(['type', 'sample_name', 'charge_total', 'x', 'y', 'phi', 'zeta', 'det', 'theta', 'run'])

        for p in self.sample_points:
            charge_total = f"{request_name}_{p['file']}"
            writer.writerow([
                SAMPLE_TYPE, p['sample_id'], charge_total,
                round(float(p['real_coords'][0]), 2), round(float(p['real_coords'][1]), 2),
                PHI, ZETA, DET, THETA, RUN_NUMBER
            ])
        
        is_success, buffer = cv2.imencode(".png", self.last_rendered_frame)
        if not is_success:
            messagebox.showerror("Save Failed", "Could not encode screenshot to PNG format.")
            return
        image_bytes = buffer.tobytes()

        try:
            os.makedirs(IMAGES_PATH, exist_ok=True)
            os.makedirs(RECEPIES_PATH, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Save Failed", f"Could not create directories:\n{e}")
            return

        csv_filename = f"{request_name}.csv"
        screenshot_filename = f"{request_name}.png"
        
        csv_filepath = os.path.join(RECEPIES_PATH, csv_filename)
        screenshot_filepath = os.path.join(IMAGES_PATH, screenshot_filename)

        print(f"\n--- Saving Files Locally ---")
        print(f"Request Name: {request_name}")
        print(f"Saving CSV to: {csv_filepath}")
        print(f"Saving Screenshot to: {screenshot_filepath}")
        print("----------------------------\n")

        try:
            with open(csv_filepath, 'w', newline='') as f:
                f.write(csv_output.getvalue())
            
            with open(screenshot_filepath, 'wb') as f:
                f.write(image_bytes)

            message = f"Files saved successfully!\n\nCSV: {os.path.abspath(csv_filepath)}\nImage: {os.path.abspath(screenshot_filepath)}"
            messagebox.showinfo("Success", message)
            
        except IOError as e:
            messagebox.showerror("Save Failed", f"An error occurred while saving files:\n{e}")

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
            point['file'] = str(i + 1).zfill(2)

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

        try:
            self.edit_data_idx = self.tree.index(self.edit_item_id)
        except ValueError:
            return
            
        self.edit_data_key = column_map[column_id]
        
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