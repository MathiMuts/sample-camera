# sample_calibrator/calibration_module.py

import cv2
import numpy as np

# --- UI Configuration ---
HEADER_HEIGHT = 80
BUTTON_WIDTH = 120
BUTTON_HEIGHT = 40
PADDING = 10

# Colors (BGR format)
COLOR_BACKGROUND = (45, 45, 45)
COLOR_BUTTON = (80, 80, 80)
COLOR_BUTTON_HOVER = (110, 110, 110)
COLOR_BUTTON_DISABLED = (60, 60, 60)
COLOR_TEXT = (230, 230, 230)
COLOR_TEXT_DISABLED = (130, 130, 130)
COLOR_POINT = (40, 40, 240) # A darker red for the points

class UIState:
    """A helper class to manage the UI state, buttons, points, and view controls."""
    def __init__(self, frame_width, frame_height):
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # Point selection state
        self.points = []
        self.confirmed = False
        
        # View control state
        self.zoom = 1.0
        self.pan_offset = np.array([0.0, 0.0]) # Top-left of view in original frame coordinates
        self.is_panning = False
        self.pan_start_pos = (0, 0)
        
        # UI interaction state
        self.hover_target = None

        # Define button rectangles (x, y, w, h)
        self.reset_button_rect = (PADDING, PADDING, BUTTON_WIDTH, BUTTON_HEIGHT)
        self.next_button_rect = (frame_width - BUTTON_WIDTH - PADDING, PADDING, BUTTON_WIDTH, BUTTON_HEIGHT)

    def check_hover(self, x, y):
        """Updates the hover target based on mouse position."""
        self.hover_target = None
        if _is_point_in_rect(x, y, self.reset_button_rect):
            self.hover_target = 'reset'
        elif _is_point_in_rect(x, y, self.next_button_rect):
            self.hover_target = 'next'


def get_three_points(cap):
    """
    Displays a camera feed with a clean UI header for selecting three points,
    including zoom and pan functionality for precision.
    """
    ret, frame = cap.read()
    frame = cv2.flip(frame, -1)
    if not ret: return None

    frame_h, frame_w, _ = frame.shape
    state = UIState(frame_w, frame_h)
    
    window_name = 'Calibration'
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, _mouse_callback, state)

    print("--- Calibration Mode ---")
    print("Use Mouse Wheel to Zoom, Middle-Click to Pan.")

    while not state.confirmed:
        ret, frame = cap.read()
        frame = cv2.flip(frame, -1)
        if not ret: break

        # Create a zoomed/panned view of the current frame
        M = np.array([[state.zoom, 0, -state.pan_offset[0] * state.zoom],
                      [0, state.zoom, -state.pan_offset[1] * state.zoom]])
        view_frame = cv2.warpAffine(frame, M, (frame_w, frame_h))

        # Create the main canvas with a header
        canvas = np.full((frame_h + HEADER_HEIGHT, frame_w, 3), COLOR_BACKGROUND, dtype=np.uint8)
        canvas[HEADER_HEIGHT:, :] = view_frame # Paste the transformed view

        _draw_ui(canvas, state, len(state.points))

        # Draw the selected points, transforming their original coordinates to the current view
        for (px, py) in state.points:
            disp_x = int((px - state.pan_offset[0]) * state.zoom)
            disp_y = int((py - state.pan_offset[1]) * state.zoom)
            cv2.circle(canvas, (disp_x, disp_y + HEADER_HEIGHT), 7, COLOR_POINT, -1)
            cv2.circle(canvas, (disp_x, disp_y + HEADER_HEIGHT), 7, COLOR_TEXT, 1)

        cv2.imshow(window_name, canvas)

        key = cv2.waitKey(20) & 0xFF
        if key == ord('q'):
            state.points = None
            break

    cv2.destroyWindow(window_name)
    return state.points if state.confirmed else None


def _mouse_callback(event, x, y, flags, state: UIState):
    """Handles all mouse events for the UI."""
    is_in_header = y < HEADER_HEIGHT

    # --- Button Clicks (Header Area) ---
    if is_in_header:
        if event == cv2.EVENT_MOUSEMOVE:
            state.check_hover(x, y)
        elif event == cv2.EVENT_LBUTTONDOWN:
            if state.hover_target == 'next' and len(state.points) == 3:
                print("Points confirmed.")
                state.confirmed = True
            elif state.hover_target == 'reset':
                print("Points reset.")
                state.points.clear()
        return # Do not process image-area events if in header

    # --- View Controls (Image Area) ---
    if event == cv2.EVENT_MBUTTONDOWN:
        state.is_panning = True
        state.pan_start_pos = np.array([x, y])
    elif event == cv2.EVENT_MOUSEMOVE and state.is_panning:
        delta = (state.pan_start_pos - np.array([x, y])) / state.zoom
        state.pan_offset += delta
        state.pan_start_pos = np.array([x, y])
    elif event == cv2.EVENT_MBUTTONUP:
        state.is_panning = False
    elif event == cv2.EVENT_MOUSEWHEEL:
        # Calculate mouse position in original frame coordinates
        mouse_pos_on_view = np.array([x, y - HEADER_HEIGHT])
        mouse_pos_orig = state.pan_offset + mouse_pos_on_view / state.zoom
        
        # Change zoom
        if flags > 0: state.zoom *= 1.2
        else: state.zoom /= 1.2
        state.zoom = np.clip(state.zoom, 1.0, 10.0)

        # Adjust pan to keep mouse position stationary
        state.pan_offset = mouse_pos_orig - mouse_pos_on_view / state.zoom

    # Clamp pan_offset to stay within reasonable bounds
    max_pan_x = state.frame_width * (1 - 1/state.zoom)
    max_pan_y = state.frame_height * (1 - 1/state.zoom)
    state.pan_offset[0] = np.clip(state.pan_offset[0], 0, max_pan_x)
    state.pan_offset[1] = np.clip(state.pan_offset[1], 0, max_pan_y)

    # Convert window click coordinates to original frame coordinates
    point_on_view = np.array([x, y - HEADER_HEIGHT])
    point_on_frame = state.pan_offset + point_on_view / state.zoom

    # --- Point Placement (Image Area) ---
    if event == cv2.EVENT_LBUTTONDOWN and len(state.points) < 3:
        orig_coords = (int(point_on_frame[0]), int(point_on_frame[1]))
        print(f"Added point at original coordinates: {orig_coords}")
        state.points.append(orig_coords)
    elif event == cv2.EVENT_RBUTTONDOWN:
        detection_radius = 15 / state.zoom # Radius is smaller when zoomed in
        point_to_remove = None
        for p in state.points:
            distance = np.linalg.norm(np.array(p) - point_on_frame)
            if distance < detection_radius:
                point_to_remove = p
                break
        if point_to_remove:
            state.points.remove(point_to_remove)
            print(f"Removed point near: {point_to_remove}")


def _draw_ui(canvas, state: UIState, num_points):
    """Draws all header buttons and text."""
    # --- Draw Buttons ---
    next_enabled = num_points == 3
    
    # Reset Button
    color = COLOR_BUTTON_HOVER if state.hover_target == 'reset' else COLOR_BUTTON
    _draw_button(canvas, "Reset", state.reset_button_rect, color, COLOR_TEXT)
    
    # Next Button
    color = COLOR_BUTTON_HOVER if state.hover_target == 'next' and next_enabled else (COLOR_BUTTON if next_enabled else COLOR_BUTTON_DISABLED)
    text_color = COLOR_TEXT if next_enabled else COLOR_TEXT_DISABLED
    _draw_button(canvas, "Next", state.next_button_rect, color, text_color)
    
    # --- Draw Status and Instruction Text ---
    status_text = f"Points: {num_points}/3"
    instruction_text = "Zoom: Mouse Wheel | Pan: Middle-Click Drag"
    
    cv2.putText(canvas, status_text, (state.reset_button_rect[0] + BUTTON_WIDTH + PADDING*2, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_TEXT, 1, cv2.LINE_AA)
    cv2.putText(canvas, instruction_text, (state.reset_button_rect[0] + BUTTON_WIDTH + PADDING*2, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1, cv2.LINE_AA)


def _draw_button(canvas, text, rect, color, text_color):
    """Helper function to draw a single button."""
    x, y, w, h = rect
    cv2.rectangle(canvas, (x, y), (x + w, y + h), color, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (0,0,0), 1)

    text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    text_x = x + (w - text_size[0]) // 2
    text_y = y + (h + text_size[1]) // 2
    cv2.putText(canvas, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 1, cv2.LINE_AA)

def _is_point_in_rect(px, py, rect):
    """Helper function to check if a point is inside a rectangle."""
    x, y, w, h = rect
    return x <= px <= x + w and y <= py <= y + h