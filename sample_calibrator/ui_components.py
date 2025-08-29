# ui_components.py

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk # Make sure ImageTk is imported

# --- UI Configuration Constants ---
SIDEBAR_WIDTH = 275
BG_COLOR = "#2d2d2d"
FG_COLOR_LIGHT = "#ffffff"
FG_COLOR_MUTED = "#cccccc"
FONT_TITLE = ("Segoe UI", 16)
FONT_BODY = ("Segoe UI", 10)
SIDEBAR_PADDING = 10 # Define padding as a constant


class UISidebar(tk.Frame):
    """A configurable sidebar widget for the application."""
    def __init__(self, parent, title, instructions, widgets_config, image_path=None):
        super().__init__(parent, width=SIDEBAR_WIDTH, bg=BG_COLOR)
        self.pack_propagate(False)

        self.created_widgets = {}

        # --- Title ---
        lbl_title = tk.Label(self, text=title, font=FONT_TITLE, bg=BG_COLOR, fg=FG_COLOR_LIGHT)
        lbl_title.pack(pady=10, padx=SIDEBAR_PADDING, anchor="w")

        # --- Dynamic Widgets (e.g., status labels) ---
        if 'status_label' in widgets_config:
            config = widgets_config['status_label']
            status_var = config.get('textvariable')
            lbl_status = tk.Label(self, textvariable=status_var, font=FONT_BODY, bg=BG_COLOR, fg=FG_COLOR_LIGHT)
            lbl_status.pack(pady=5, padx=SIDEBAR_PADDING, anchor="w")
            self.created_widgets['status_label'] = lbl_status

        # --- Instructions ---
        lbl_inst = tk.Label(self, text=instructions, justify=tk.LEFT, wraplength=SIDEBAR_WIDTH-(SIDEBAR_PADDING*2), font=FONT_BODY, bg=BG_COLOR, fg=FG_COLOR_MUTED)
        lbl_inst.pack(pady=20, padx=SIDEBAR_PADDING, anchor="w", fill="x")

        # --- HELP IMAGE (NEW LOGIC) ---
        if image_path:
            try:
                # Calculate target width based on sidebar width and padding
                target_width = SIDEBAR_WIDTH - (SIDEBAR_PADDING * 2)

                # Open and resize the image while maintaining aspect ratio
                original_image = Image.open(image_path)
                w, h = original_image.size
                aspect_ratio = h / w
                target_height = int(target_width * aspect_ratio)

                resized_image = original_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                # Convert to Tkinter-compatible image
                self.help_photo = ImageTk.PhotoImage(resized_image)

                # Create and pack the label
                lbl_image = tk.Label(self, image=self.help_photo, bg=BG_COLOR)
                # The .image attribute is a tkinter quirk to prevent garbage collection
                lbl_image.image = self.help_photo 
                lbl_image.pack(pady=(0, 20), padx=SIDEBAR_PADDING)

            except FileNotFoundError:
                print(f"Warning: Help image not found at '{image_path}'")
            except Exception as e:
                print(f"Error loading help image: {e}")

        # --- Bottom Buttons ---
        button_frame = tk.Frame(self, bg=BG_COLOR)
        button_frame.pack(side="bottom", pady=20, padx=SIDEBAR_PADDING, fill="x")

        if 'buttons' in widgets_config:
            buttons = widgets_config['buttons']
            num_buttons = len(buttons)
            for i, btn_config in enumerate(buttons):
                btn = ttk.Button(button_frame, text=btn_config['text'], command=btn_config['command'])
                
                if num_buttons == 1:
                    btn.pack(side="right", fill="x")
                else:
                    side = "left" if i == 0 else "right"
                    padx = (0, 5) if i == 0 else (5, 0)
                    btn.pack(side=side, expand=True, padx=padx)

                self.created_widgets[btn_config['text']] = btn


class BaseUIState:
    """A base class for UI state, handling view controls."""
    def __init__(self, frame_width, frame_height):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.zoom = 1.0
        self.pan_offset = np.array([0.0, 0.0])
        self.is_panning = False
        self.pan_start_pos = (0, 0)

def handle_view_controls(event, x, y, flags, state: BaseUIState):
    """
    Processes mouse events for zoom and pan.
    Expects 'x' and 'y' to be relative to the camera view's top-left corner.
    """
    point_on_view = np.array([x, y])
    
    if event == cv2.EVENT_MBUTTONDOWN:
        state.is_panning = True
        state.pan_start_pos = point_on_view / state.zoom + state.pan_offset
    elif event == cv2.EVENT_MOUSEMOVE and state.is_panning:
        state.pan_offset = state.pan_start_pos - point_on_view / state.zoom
    elif event == cv2.EVENT_MBUTTONUP:
        state.is_panning = False
    elif event == cv2.EVENT_MOUSEWHEEL:
        mouse_pos_orig = state.pan_offset + point_on_view / state.zoom
        
        if flags > 0: new_zoom = state.zoom * 1.2
        else: new_zoom = state.zoom / 1.2
        new_zoom = np.clip(new_zoom, 1.0, 10.0)
        
        state.pan_offset = mouse_pos_orig - point_on_view / new_zoom
        state.zoom = new_zoom

    # Clamp pan_offset
    max_pan_x = state.frame_width * (1 - 1/state.zoom)
    max_pan_y = state.frame_height * (1 - 1/state.zoom)
    state.pan_offset[0] = np.clip(state.pan_offset[0], 0, max_pan_x)
    state.pan_offset[1] = np.clip(state.pan_offset[1], 0, max_pan_y)
    
    point_on_frame = state.pan_offset + point_on_view / state.zoom
    return point_on_frame