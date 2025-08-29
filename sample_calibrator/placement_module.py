# sample_calibrator/placement_module.py

import cv2
import numpy as np
from itertools import combinations
import ui_components

COLOR_RECTANGLE = (0, 255, 0)

class PlacementUIState(ui_components.BaseUIState):
    def __init__(self, frame_width, frame_height):
        super().__init__(frame_width, frame_height)
        self.hover_target = None
        self.back_clicked = False
        self.next_clicked = False
        total_width = frame_width + ui_components.SIDEBAR_WIDTH
        self.back_button_rect = (ui_components.SIDEBAR_WIDTH + ui_components.PADDING, ui_components.PADDING, ui_components.BUTTON_WIDTH, ui_components.BUTTON_HEIGHT)
        self.next_button_rect = (total_width - ui_components.BUTTON_WIDTH - ui_components.PADDING, ui_components.PADDING, ui_components.BUTTON_WIDTH, ui_components.BUTTON_HEIGHT)

    def check_hover(self, x, y):
        self.hover_target = None
        if ui_components.is_point_in_rect(x, y, self.back_button_rect): self.hover_target = 'back'
        elif ui_components.is_point_in_rect(x, y, self.next_button_rect): self.hover_target = 'next'

def place_rectangle(cap, calibrated_points):
    ret, frame = cap.read()
    frame = cv2.flip(frame, -1)
    if not ret: return (None, None)

    frame_h, frame_w, _ = frame.shape
    state = PlacementUIState(frame_w, frame_h)
    
    window_name = 'Placement | Step 2 of 3'
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, _mouse_callback, state)

    final_rectangle_box = None
    while not (state.back_clicked or state.next_clicked):
        ret, frame = cap.read()
        frame = cv2.flip(frame, -1)
        if not ret: break

        canvas = ui_components.create_application_canvas(frame.shape)
        
        # Draw the rectangle on the original frame first
        drawing_frame = frame.copy()
        final_rectangle_box = _calculate_and_draw_rectangle(drawing_frame, calibrated_points)

        M = np.array([[state.zoom, 0, -state.pan_offset[0] * state.zoom],
                      [0, state.zoom, -state.pan_offset[1] * state.zoom]])
        view_frame = cv2.warpAffine(drawing_frame, M, (frame_w, frame_h))

        canvas[ui_components.HEADER_HEIGHT:, ui_components.SIDEBAR_WIDTH:] = view_frame
        _draw_ui(canvas, state)
        cv2.imshow(window_name, canvas)

        key = cv2.waitKey(20) & 0xFF
        if key == ord('q'): return (None, None)
        elif key == ord('f'):
            state.is_fullscreen = not state.is_fullscreen
            fs_flag = cv2.WINDOW_FULLSCREEN if state.is_fullscreen else cv2.WINDOW_AUTOSIZE
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, fs_flag)

    cv2.destroyWindow(window_name)
    if state.back_clicked: return ('back', None)
    if state.next_clicked: return ('success', final_rectangle_box)
    return (None, None)
# ... (Include the _mouse_callback, _draw_ui, and calculation functions, adapted to the simple, fixed layout)
def _mouse_callback(event, x, y, flags, state: PlacementUIState):
    is_in_header = y < ui_components.HEADER_HEIGHT
    is_in_sidebar = x < ui_components.SIDEBAR_WIDTH
    if is_in_header:
        if event == cv2.EVENT_MOUSEMOVE: state.check_hover(x, y)
        elif event == cv2.EVENT_LBUTTONDOWN:
            if state.hover_target == 'back': state.back_clicked = True
            elif state.hover_target == 'next': state.next_clicked = True
        return
    if is_in_sidebar: return
    corrected_x = x - ui_components.SIDEBAR_WIDTH
    corrected_y = y - ui_components.HEADER_HEIGHT
    ui_components.handle_view_controls(event, corrected_x, corrected_y, flags, state)

def _draw_ui(canvas, state: PlacementUIState):
    back_color = ui_components.COLOR_BUTTON_HOVER if state.hover_target == 'back' else ui_components.COLOR_BUTTON
    ui_components.draw_button(canvas, "Back", state.back_button_rect, back_color, ui_components.COLOR_TEXT)
    next_color = ui_components.COLOR_BUTTON_HOVER if state.hover_target == 'next' else ui_components.COLOR_BUTTON
    ui_components.draw_button(canvas, "Next", state.next_button_rect, next_color, ui_components.COLOR_TEXT)
    text_start_x = ui_components.SIDEBAR_WIDTH + ui_components.PADDING
    title_text, status_text = "Step 2: Placement Confirmation", "Reviewing calculated rectangle."
    instruction_1 = "Confirm the green rectangle is correct or go Back to re-calibrate."
    instruction_2 = "Zoom: Mouse Wheel | Pan: Middle-Click Drag"
    cv2.putText(canvas, title_text, (text_start_x, ui_components.Y_TITLE), cv2.FONT_HERSHEY_SIMPLEX, 0.8, ui_components.COLOR_TEXT, 2, cv2.LINE_AA)
    cv2.putText(canvas, status_text, (text_start_x, ui_components.Y_STATUS), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ui_components.COLOR_TEXT, 1, cv2.LINE_AA)
    cv2.putText(canvas, instruction_1, (text_start_x, ui_components.Y_INSTRUCTION_1), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1, cv2.LINE_AA)
    cv2.putText(canvas, instruction_2, (text_start_x, ui_components.Y_INSTRUCTION_2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1, cv2.LINE_AA)
# (Your _calculate_... functions go here)
def _calculate_circumcenter(pts):
    p1, p2, p3 = pts[0], pts[1], pts[2]
    D = 2 * (p1[0] * (p2[1] - p3[1]) + p2[0] * (p3[1] - p1[1]) + p3[0] * (p1[1] - p2[1]))
    if abs(D) < 1e-6: return None
    ux = ((p1[0]**2 + p1[1]**2) * (p2[1] - p3[1]) + (p2[0]**2 + p2[1]**2) * (p3[1] - p1[1]) + (p3[0]**2 + p3[1]**2) * (p1[1] - p2[1])) / D
    uy = ((p1[0]**2 + p1[1]**2) * (p3[0] - p2[0]) + (p2[0]**2 + p2[1]**2) * (p1[0] - p3[0]) + (p3[0]**2 + p3[1]**2) * (p2[0] - p1[0])) / D
    return (int(ux), int(uy))

def _calculate_and_draw_rectangle(frame, points):
    if len(points) != 3: return
    pts_np = np.array(points)
    point_pairs = combinations(pts_np, 2)
    distances = [np.linalg.norm(p1 - p2) for p1, p2 in point_pairs]
    average_distance = np.mean(distances)
    scaling_actor = average_distance / 142.408
    side_x, side_y = 130 * scaling_actor, 120 * scaling_actor
    center = _calculate_circumcenter(pts_np)
    if center is None: return
    sorted_indices = np.argsort(pts_np[:, 0])
    sorted_pts = pts_np[sorted_indices]
    p_mid, p_right = sorted_pts[1], sorted_pts[2]
    dy, dx = p_right[1] - p_mid[1], p_right[0] - p_mid[0]
    angle = np.degrees(np.arctan2(dy, dx)) + 5.25
    rect = (center, (side_y, side_x), angle)
    box = np.int32(cv2.boxPoints(rect))
    cv2.drawContours(frame, [box], 0, COLOR_RECTANGLE, 2)
    return box