# sample_calibrator/placement_module.py

import cv2
import numpy as np
from itertools import combinations

# --- UI Configuration (same as calibration_module for consistency) ---
HEADER_HEIGHT = 80
BUTTON_WIDTH = 120
BUTTON_HEIGHT = 40
PADDING = 10

# Colors (BGR format)
COLOR_BACKGROUND = (45, 45, 45)
COLOR_BUTTON = (80, 80, 80)
COLOR_BUTTON_HOVER = (110, 110, 110)
COLOR_TEXT = (230, 230, 230)
COLOR_RECTANGLE = (0, 255, 0) # Green for the rectangle
COLOR_CONSTRUCTION = (0, 255, 255) # Yellow for construction lines/points

class PlacementUIState:
    """A helper class to manage the UI state for the placement step."""
    def __init__(self, frame_width, frame_height):
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # Button/Flow state
        self.hover_target = None
        self.back_clicked = False
        self.next_clicked = False
        
        # Define button rectangles (x, y, w, h)
        self.back_button_rect = (PADDING, PADDING, BUTTON_WIDTH, BUTTON_HEIGHT)
        self.next_button_rect = (frame_width - BUTTON_WIDTH - PADDING, PADDING, BUTTON_WIDTH, BUTTON_HEIGHT)

    def check_hover(self, x, y):
        """Updates the hover target based on mouse position."""
        self.hover_target = None
        if _is_point_in_rect(x, y, self.back_button_rect):
            self.hover_target = 'back'
        elif _is_point_in_rect(x, y, self.next_button_rect):
            self.hover_target = 'next'


def place_rectangle(cap, calibrated_points):
    """
    Displays a camera feed and draws a rectangle based on the three calibrated points.
    Provides 'Back' and 'Next' options.
    
    Returns:
        str: 'back' if the user wants to re-calibrate,
             'success' if the user confirms,
             None if the user quits.
    """
    ret, frame = cap.read()
    frame = cv2.flip(frame, -1)
    if not ret: return None

    frame_h, frame_w, _ = frame.shape
    state = PlacementUIState(frame_w, frame_h)
    
    window_name = 'Placement'
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, _mouse_callback, state)

    print("\n--- Placement Mode ---")
    print("Confirm the placement of the rectangle.")

    while not (state.back_clicked or state.next_clicked):
        ret, frame = cap.read()
        frame = cv2.flip(frame, -1)
        if not ret: break

        # Create the main canvas with a header
        canvas = np.full((frame_h + HEADER_HEIGHT, frame_w, 3), COLOR_BACKGROUND, dtype=np.uint8)
        
        # Calculate and draw the rectangle and its construction lines.
        _calculate_and_draw_rectangle(frame, calibrated_points)
        
        # Paste the camera frame onto the canvas
        canvas[HEADER_HEIGHT:, :] = frame

        _draw_ui(canvas, state)

        cv2.imshow(window_name, canvas)

        key = cv2.waitKey(20) & 0xFF
        if key == ord('q'):
            return None # User quit

    cv2.destroyWindow(window_name)
    
    if state.back_clicked:
        return 'back'
    if state.next_clicked:
        return 'success'
    return None


def _calculate_circumcenter(pts):
    """
    Calculates the center of the circle passing through three points (circumcenter).
    """
    p1, p2, p3 = pts[0], pts[1], pts[2]
    
    # Mathematical formula for the circumcenter
    D = 2 * (p1[0] * (p2[1] - p3[1]) + p2[0] * (p3[1] - p1[1]) + p3[0] * (p1[1] - p2[1]))
    
    # Avoid division by zero if points are collinear
    if D == 0:
        return None

    ux = ((p1[0]**2 + p1[1]**2) * (p2[1] - p3[1]) + (p2[0]**2 + p2[1]**2) * (p3[1] - p1[1]) + (p3[0]**2 + p3[1]**2) * (p1[1] - p2[1])) / D
    uy = ((p1[0]**2 + p1[1]**2) * (p3[0] - p2[0]) + (p2[0]**2 + p2[1]**2) * (p1[0] - p3[0]) + (p3[0]**2 + p3[1]**2) * (p2[0] - p1[0])) / D
    
    return (int(ux), int(uy))


def _draw_crosshair(frame, center, color, size=10, thickness=1):
    """Draws a crosshair at the specified center point."""
    x, y = center
    cv2.line(frame, (x - size, y), (x + size, y), color, thickness)
    cv2.line(frame, (x, y - size), (x, y + size), color, thickness)

def _draw_dotted_line(frame, pt1, pt2, color, dot_radius=2, gap=15):
    """Draws a dotted line on the frame using circles."""
    pt1 = np.array(pt1)
    pt2 = np.array(pt2)
    dist = np.linalg.norm(pt1 - pt2)
    
    if dist < gap: return

    # Calculate number of dots
    num_dots = int(dist / gap)
    if num_dots == 0: return

    for i in range(num_dots + 1):
        alpha = i / num_dots
        x = int(pt1[0] * (1 - alpha) + pt2[0] * alpha)
        y = int(pt1[1] * (1 - alpha) + pt2[1] * alpha)
        cv2.circle(frame, (x, y), dot_radius, color, -1)


def _calculate_and_draw_rectangle(frame, points):
    """
    Calculates the rectangle based on the 3 points and draws it on the frame.
    Also draws the construction lines and points used for the calculation.
    """
    if len(points) != 3:
        return

    # Convert points to a numpy array for cv2 functions
    # NOTE: points = [(220, 84), (498, 223), (240, 394)]
    pts_np = np.array(points, dtype=np.int32)

    # --- Visualization: Draw the 3 initial calibration points ---
    for pt in pts_np:
        cv2.circle(frame, tuple(pt), 5, COLOR_CONSTRUCTION, -1)

    point_pairs = combinations(pts_np, 2)
    distances = [np.linalg.norm(p1 - p2) for p1, p2 in point_pairs]
    average_distance = np.mean(distances)
    
    scaling_actor = average_distance / 142.408 # = pixels / mm
    
    side_x = 130 * scaling_actor
    side_y = 120 * scaling_actor
    
    center = _calculate_circumcenter(pts_np)
    
    if center is None:
        return

    # --- Visualization: Draw the calculated circumcenter ---
    _draw_crosshair(frame, center, COLOR_CONSTRUCTION, size=10, thickness=2)
    
    # Sort points based on their x-coordinate
    # argsort() returns the indices that would sort based on the x-values (pts_np[:, 0])
    sorted_indices = np.argsort(pts_np[:, 0])
    sorted_pts = pts_np[sorted_indices]

    # The two points that are not the absolute leftmost point are used to determine the angle.
    # This provides a stable line, presumably along one edge of the object.
    p_mid = sorted_pts[1]
    p_right = sorted_pts[2]

    # --- Visualization: Draw the line used for angle calculation ---
    _draw_dotted_line(frame, tuple(p_mid), tuple(p_right), COLOR_CONSTRUCTION)

    # Calculate the angle of the line connecting these two points
    # We use atan2 for a stable angle calculation in all quadrants
    dy = p_right[1] - p_mid[1]
    dx = p_right[0] - p_mid[0]
    angle_rad = np.arctan2(dy, dx)
    
    # Convert angle from radians to degrees for OpenCV
    angle_deg = np.degrees(angle_rad)
    
    angle = angle_deg + 5
    
    # 3. Create the rotated rectangle object
    # Format: ((center_x, center_y), (width, height), angle_in_degrees)
    rect = (center, (side_y, side_x), angle)
    
    # 4. Get the 4 corner points of this rotated rectangle
    box = cv2.boxPoints(rect)
    box = np.int32(box)  # Convert corner points to integers

    # 5. Draw the final rectangle on the frame
    cv2.drawContours(frame, [box], 0, COLOR_RECTANGLE, 2)


def _mouse_callback(event, x, y, flags, state: PlacementUIState):
    """Handles mouse events for the placement UI."""
    is_in_header = y < HEADER_HEIGHT
    if not is_in_header:
        return

    if event == cv2.EVENT_MOUSEMOVE:
        state.check_hover(x, y)
    elif event == cv2.EVENT_LBUTTONDOWN:
        if state.hover_target == 'back':
            print("Back to calibration.")
            state.back_clicked = True
        elif state.hover_target == 'next':
            print("Placement confirmed.")
            state.next_clicked = True

def _draw_ui(canvas, state: PlacementUIState):
    """Draws all header buttons and text for the placement screen."""
    # Back Button
    color = COLOR_BUTTON_HOVER if state.hover_target == 'back' else COLOR_BUTTON
    _draw_button(canvas, "Back", state.back_button_rect, color, COLOR_TEXT)
    
    # Next Button
    color = COLOR_BUTTON_HOVER if state.hover_target == 'next' else COLOR_BUTTON
    _draw_button(canvas, "Next", state.next_button_rect, color, COLOR_TEXT)
    
    # Instruction Text
    instruction_text = "Confirm the green rectangle or go Back to re-calibrate."
    text_size, _ = cv2.getTextSize(instruction_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)
    text_x = (state.frame_width - text_size[0]) // 2
    cv2.putText(canvas, instruction_text, (text_x, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_TEXT, 1, cv2.LINE_AA)


# --- Helper functions copied from calibration_module ---

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