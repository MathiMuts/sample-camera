# sample_calibrator/ui_components.py

import cv2
import numpy as np

class BaseUIState:
    """A base class for UI state, handling view controls and fullscreen state."""
    def __init__(self, frame_width, frame_height):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.zoom = 1.0
        self.pan_offset = np.array([0.0, 0.0])
        self.is_panning = False
        self.pan_start_pos = (0, 0)
        # is_fullscreen is now managed by Tkinter window state

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
        
        # In Tkinter, positive delta is scroll up (zoom in)
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