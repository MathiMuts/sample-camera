# sample_calibrator/ui_components.py

import cv2
import numpy as np

# --- Shared UI Configuration ---
HEADER_HEIGHT = 160
SIDEBAR_WIDTH = 250
BUTTON_WIDTH = 120
BUTTON_HEIGHT = 40
PADDING = 10

# Absolute Y-coordinates for a consistent text layout
Y_TITLE = 35
Y_STATUS = 70
Y_INSTRUCTION_1 = 100
Y_INSTRUCTION_2 = 125

# Colors (BGR format)
COLOR_BACKGROUND = (45, 45, 45)
COLOR_SIDEBAR = (35, 35, 35)
COLOR_BUTTON = (80, 80, 80)
COLOR_BUTTON_HOVER = (110, 110, 110)
COLOR_BUTTON_DISABLED = (60, 60, 60)
COLOR_TEXT = (230, 230, 230)
COLOR_TEXT_DISABLED = (130, 130, 130)

class BaseUIState:
    """A base class for UI state, handling view controls and fullscreen state."""
    def __init__(self, frame_width, frame_height):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.zoom = 1.0
        self.pan_offset = np.array([0.0, 0.0])
        self.is_panning = False
        self.pan_start_pos = (0, 0)
        self.is_fullscreen = False

def create_application_canvas(frame_shape):
    """Creates the main application canvas with a fixed Header and Sidebar."""
    frame_h, frame_w, _ = frame_shape
    total_w = frame_w + SIDEBAR_WIDTH
    total_h = frame_h + HEADER_HEIGHT
    
    # Create the main canvas with the background color
    canvas = np.full((total_h, total_w, 3), COLOR_BACKGROUND, dtype=np.uint8)

    # Draw the sidebar
    cv2.rectangle(canvas, (0, HEADER_HEIGHT), (SIDEBAR_WIDTH, total_h), COLOR_SIDEBAR, -1)
    
    return canvas

def handle_view_controls(event, x, y, flags, state: BaseUIState):
    """
    Processes mouse events for zoom and pan.
    Expects 'x' and 'y' to be relative to the camera view's top-left corner.
    """
    # Use the coordinates relative to the viewport, not the whole canvas
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
    
    # Return the calculated point on the original, unzoomed frame
    point_on_frame = state.pan_offset + point_on_view / state.zoom
    return point_on_frame

def draw_button(canvas, text, rect, color, text_color):
    """Helper function to draw a single button."""
    x, y, w, h = rect
    cv2.rectangle(canvas, (x, y), (x + w, y + h), color, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (0,0,0), 1)
    text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    text_x = x + (w - text_size[0]) // 2
    text_y = y + (h + text_size[1]) // 2
    cv2.putText(canvas, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 1, cv2.LINE_AA)

def is_point_in_rect(px, py, rect):
    """Helper function to check if a point is inside a rectangle."""
    x, y, w, h = rect
    return x <= px <= x + w and y <= py <= y + h