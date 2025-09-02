# ui_components.py

"""
This module provides shared, reusable components for the application's UI.

It contains:
- UI style constants (colors, fonts, sizes).
- `UISidebar`: A standardized sidebar class that can be configured with a
  title, instructions, an image, and different button layouts.
- `BaseUIState`: A simple class to store and manage the state of the view
  (zoom level, pan offset).
- `handle_view_controls`: A core function that processes mouse events to
  implement interactive pan and zoom functionality for any video feed.
"""

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk

# --- UI Configuration Constants ---
SIDEBAR_WIDTH = 600
BG_COLOR = "#2d2d2d"
FG_COLOR_LIGHT = "#ffffff"
FG_COLOR_MUTED = "#cccccc"
FONT_TITLE = ("Segoe UI", 24)
FONT_BODY = ("Segoe UI", 14)
SIDEBAR_PADDING = 10 


class UISidebar(tk.Frame):
    """A configurable sidebar widget for the application."""
    def __init__(self, parent, title, instructions, widgets_config, image_path=None):
        super().__init__(parent, width=SIDEBAR_WIDTH, bg=BG_COLOR)
        self.pack_propagate(False) # Prevents the sidebar from resizing to fit its contents.

        self.created_widgets = {}

        lbl_title = tk.Label(self, text=title, font=FONT_TITLE, bg=BG_COLOR, fg=FG_COLOR_LIGHT)
        lbl_title.pack(pady=10, padx=SIDEBAR_PADDING, anchor="w")

        if 'status_label' in widgets_config:
            config = widgets_config['status_label']
            status_var = config.get('textvariable')
            lbl_status = tk.Label(self, textvariable=status_var, font=FONT_BODY, bg=BG_COLOR, fg=FG_COLOR_LIGHT)
            lbl_status.pack(pady=5, padx=SIDEBAR_PADDING, anchor="w")
            self.created_widgets['status_label'] = lbl_status

        lbl_inst = tk.Label(self, text=instructions, justify=tk.LEFT, wraplength=SIDEBAR_WIDTH-(SIDEBAR_PADDING*2), font=FONT_BODY, bg=BG_COLOR, fg=FG_COLOR_MUTED)
        lbl_inst.pack(pady=20, padx=SIDEBAR_PADDING, anchor="w", fill="x")

        if image_path:
            try:
                target_width = SIDEBAR_WIDTH - (SIDEBAR_PADDING * 2)
                original_image = Image.open(image_path)
                w, h = original_image.size
                aspect_ratio = h / w
                target_height = int(target_width * aspect_ratio)
                resized_image = original_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                self.help_photo = ImageTk.PhotoImage(resized_image)
                lbl_image = tk.Label(self, image=self.help_photo, bg=BG_COLOR)
                # This is a tkinter quirk to prevent the image from being garbage collected.
                lbl_image.image = self.help_photo 
                lbl_image.pack(pady=(0, 20), padx=SIDEBAR_PADDING)

            except FileNotFoundError:
                print(f"Warning: Help image not found at '{image_path}'")
            except Exception as e:
                print(f"Error loading help image: {e}")

        button_frame = tk.Frame(self, bg=BG_COLOR)
        button_frame.pack(side="bottom", pady=20, padx=SIDEBAR_PADDING, fill="x")

        if 'buttons' in widgets_config:
            style = ttk.Style(self)
            style.configure('Sidebar.TButton', font=FONT_BODY)

            buttons = widgets_config['buttons']
            num_buttons = len(buttons)
            for i, btn_config in enumerate(buttons):
                btn = ttk.Button(button_frame, text=btn_config['text'], command=btn_config['command'], style='Sidebar.TButton')
                
                if num_buttons == 1:
                    btn.pack(side="right", fill="x")
                else:
                    side = "left" if i == 0 else "right"
                    padx = (0, 5) if i == 0 else (5, 0)
                    btn.pack(side=side, expand=True, padx=padx, ipadx=15, ipady=5)

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
    """Processes mouse events for zoom and pan."""
    point_on_view = np.array([x, y])
    
    if event == cv2.EVENT_MBUTTONDOWN:
        state.is_panning = True
        state.pan_start_pos = point_on_view / state.zoom + state.pan_offset
    elif event == cv2.EVENT_MOUSEMOVE and state.is_panning:
        state.pan_offset = state.pan_start_pos - point_on_view / state.zoom
    elif event == cv2.EVENT_MBUTTONUP:
        state.is_panning = False
    elif event == cv2.EVENT_MOUSEWHEEL:
        # Calculate where the mouse is on the original frame before zooming.
        mouse_pos_orig = state.pan_offset + point_on_view / state.zoom
        
        if flags > 0: new_zoom = state.zoom * 1.2
        else: new_zoom = state.zoom / 1.2
        new_zoom = np.clip(new_zoom, 1.0, 10.0) # Limit zoom level.
        
        # Adjust pan offset to keep the point under the cursor stationary ("zoom to cursor").
        state.pan_offset = mouse_pos_orig - point_on_view / new_zoom
        state.zoom = new_zoom

    # Prevent panning beyond the edges of the original frame.
    max_pan_x = state.frame_width * (1 - 1/state.zoom)
    max_pan_y = state.frame_height * (1 - 1/state.zoom)
    state.pan_offset[0] = np.clip(state.pan_offset[0], 0, max_pan_x)
    state.pan_offset[1] = np.clip(state.pan_offset[1], 0, max_pan_y)
    
    # Return the coordinates of the event on the original, un-transformed frame.
    point_on_frame = state.pan_offset + point_on_view / state.zoom
    return point_on_frame