# sample_calibrator/calibration_module.py

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
import ui_components

COLOR_POINT = (40, 40, 240) # BGR

class CalibrationFrame(tk.Frame):
    def __init__(self, parent, controller, cap):
        # We'll keep the borderless frame for good measure
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        
        self.controller = controller
        self.cap = cap

        self.ui_state = None 
        self.points = []
        
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # --- THE DEFINITIVE FIX IS HERE ---
        # Anchor the image to the North-West (top-left) corner of the Label.
        # This prevents the Label from centering the image and creating a margin.
        self.video_label = tk.Label(self, borderwidth=0, highlightthickness=0, anchor=tk.NW)
        
        self.video_label.grid(row=0, column=0, sticky="nsew")

        sidebar = tk.Frame(self, width=250, bg="#2d2d2d")
        sidebar.grid(row=0, column=1, sticky="ns")
        
        lbl_title = tk.Label(sidebar, text="Step 1: Calibrate", font=("Segoe UI", 16), bg="#2d2d2d", fg="white")
        lbl_title.pack(pady=10, padx=10, anchor="w")

        self.lbl_status = tk.Label(sidebar, text="Points Selected: 0/3", font=("Segoe UI", 10), bg="#2d2d2d", fg="white")
        self.lbl_status.pack(pady=5, padx=10, anchor="w")

        instructions = (
            "Click on the three designated corners.\n\n"
            "Zoom: Mouse Wheel\n"
            "Pan: Middle-Click Drag\n"
            "Remove Point: Right-Click"
        )
        lbl_inst = tk.Label(sidebar, text=instructions, justify=tk.LEFT, font=("Segoe UI", 10), bg="#2d2d2d", fg="#cccccc")
        lbl_inst.pack(pady=20, padx=10, fill="x")

        self.next_button = ttk.Button(sidebar, text="Next", command=self.on_next, state="disabled")
        self.next_button.pack(side="bottom", pady=20, padx=10, fill="x")
        
        self.video_label.bind("<Button-1>", self.on_left_click)
        self.video_label.bind("<Button-3>", self.on_right_click)
        self.video_label.bind("<ButtonPress-2>", self.on_pan_start)
        self.video_label.bind("<ButtonRelease-2>", self.on_pan_end)
        self.video_label.bind("<B2-Motion>", self.on_pan_move)
        self.video_label.bind("<MouseWheel>", self.on_mouse_wheel)

        self._is_active = False

    # ... The rest of the file remains exactly the same. No logic changes are needed. ...
    def on_show(self):
        self._is_active = True
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
        if not self._is_active or not self.ui_state:
            return

        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, -1)
            drawing_frame = frame.copy()
            
            M = np.array([[self.ui_state.zoom, 0, -self.ui_state.pan_offset[0] * self.ui_state.zoom],
                          [0, self.ui_state.zoom, -self.ui_state.pan_offset[1] * self.ui_state.zoom]])
            view_frame = cv2.warpAffine(drawing_frame, M, (self.ui_state.frame_width, self.ui_state.frame_height))

            for (px, py) in self.points:
                disp_x = int((px - self.ui_state.pan_offset[0]) * self.ui_state.zoom)
                disp_y = int((py - self.ui_state.pan_offset[1]) * self.ui_state.zoom)
                cv2.circle(view_frame, (disp_x, disp_y), 7, COLOR_POINT, -1)
                cv2.circle(view_frame, (disp_x, disp_y), 7, (255, 255, 255), 1)

            img = cv2.cvtColor(view_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img)
            self.imgtk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.config(image=self.imgtk)

        self.after(15, self.video_loop)

    def on_left_click(self, event):
        if len(self.points) >= 3 or not self.ui_state: return
        point_on_frame = ui_components.handle_view_controls(cv2.EVENT_LBUTTONDOWN, event.x, event.y, 0, self.ui_state)
        print(f"Added point at: ({point_on_frame[0]:.2f}, {point_on_frame[1]:.2f})")
        self.points.append((point_on_frame[0], point_on_frame[1]))
        self.update_ui()

    def on_right_click(self, event):
        if not self.ui_state: return
        point_on_frame = ui_components.handle_view_controls(cv2.EVENT_RBUTTONDOWN, event.x, event.y, 0, self.ui_state)
        detection_radius = 15 / self.ui_state.zoom
        point_to_remove = None
        for p in self.points:
            if np.linalg.norm(np.array(p) - point_on_frame) < detection_radius:
                point_to_remove = p
                break
        if point_to_remove:
            self.points.remove(point_to_remove)
            print(f"Removed point near: ({point_to_remove[0]:.2f}, {point_to_remove[1]:.2f})")
        self.update_ui()

    def on_pan_start(self, event):
        if not self.ui_state: return
        ui_components.handle_view_controls(cv2.EVENT_MBUTTONDOWN, event.x, event.y, 0, self.ui_state)

    def on_pan_end(self, event):
        if not self.ui_state: return
        ui_components.handle_view_controls(cv2.EVENT_MBUTTONUP, event.x, event.y, 0, self.ui_state)

    def on_pan_move(self, event):
        if not self.ui_state: return
        ui_components.handle_view_controls(cv2.EVENT_MOUSEMOVE, event.x, event.y, 0, self.ui_state)

    def on_mouse_wheel(self, event):
        if not self.ui_state: return
        ui_components.handle_view_controls(cv2.EVENT_MOUSEWHEEL, event.x, event.y, event.delta, self.ui_state)

    def update_ui(self):
        self.lbl_status.config(text=f"Points Selected: {len(self.points)}/3")
        self.next_button.config(state="normal" if len(self.points) == 3 else "disabled")

    def on_next(self):
        self.on_hide()
        self.controller.calibration_complete(self.points)