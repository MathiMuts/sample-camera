# sample_calibrator/sample_positions_module.py

import cv2
import numpy as np
import ui_components

GRID_ROWS, GRID_COLS = 8, 12
COLOR_RECTANGLE_BORDER = (0, 255, 0)
COLOR_GRID_POINT = (255, 100, 0)

class SamplePositionsUIState(ui_components.BaseUIState):
    def __init__(self, frame_width, frame_height):
        super().__init__(frame_width, frame_height)
        self.hover_target = None
        self.back_clicked = False
        self.back_button_rect = (ui_components.SIDEBAR_WIDTH + ui_components.PADDING, ui_components.PADDING, ui_components.BUTTON_WIDTH, ui_components.BUTTON_HEIGHT)

    def check_hover(self, x, y):
        self.hover_target = None
        if ui_components.is_point_in_rect(x, y, self.back_button_rect): self.hover_target = 'back'

def show_sample_positions(cap, rectangle_corners):
    ret, frame = cap.read()
    frame = cv2.flip(frame, -1)
    if not ret: return None

    frame_h, frame_w, _ = frame.shape
    state = SamplePositionsUIState(frame_w, frame_h)
    
    window_name = 'Sample Positions | Step 3 of 3'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, _mouse_callback, state)

    print("\n--- Sample Positions Mode ---")
    print("Press 'f' to toggle fullscreen. Press 'q' to finish.")

    while not state.back_clicked:
        ret, frame = cap.read()
        frame = cv2.flip(frame, -1)
        if not ret: break

        drawing_frame = frame.copy()
        _draw_grid_on_rectangle(drawing_frame, rectangle_corners)

        M = np.array([[state.zoom, 0, -state.pan_offset[0] * state.zoom],
                      [0, state.zoom, -state.pan_offset[1] * state.zoom]])
        view_frame = cv2.warpAffine(drawing_frame, M, (frame_w, frame_h))

        canvas = ui_components.create_application_canvas(view_frame, frame.shape)
        _draw_ui(canvas, state)
        cv2.imshow(window_name, canvas)

        key = cv2.waitKey(20) & 0xFF
        if key == ord('q'):
            cv2.destroyWindow(window_name)
            return 'success'
        elif key == ord('f'):
            state.is_fullscreen = not state.is_fullscreen
            fullscreen_flag = cv2.WINDOW_FULLSCREEN if state.is_fullscreen else cv2.WINDOW_NORMAL
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, fullscreen_flag)

    cv2.destroyWindow(window_name)
    return 'back'

def _mouse_callback(event, x, y, flags, state: SamplePositionsUIState):
    is_in_header = y < ui_components.HEADER_HEIGHT
    is_in_sidebar = x < ui_components.SIDEBAR_WIDTH

    if is_in_header:
        if event == cv2.EVENT_MOUSEMOVE: state.check_hover(x, y)
        elif event == cv2.EVENT_LBUTTONDOWN:
            if state.hover_target == 'back': state.back_clicked = True
        return

    if is_in_sidebar: return
    
    corrected_x = x - ui_components.SIDEBAR_WIDTH
    corrected_y = y
    ui_components.handle_view_controls(event, corrected_x, corrected_y, flags, state)

def _draw_ui(canvas, state: SamplePositionsUIState):
    color = ui_components.COLOR_BUTTON_HOVER if state.hover_target == 'back' else ui_components.COLOR_BUTTON
    ui_components.draw_button(canvas, "Back", state.back_button_rect, color, ui_components.COLOR_TEXT)
    
    text_start_x = ui_components.SIDEBAR_WIDTH + ui_components.PADDING
    
    title_text = "Step 3: Final Confirmation"
    status_text = "Sample grid is now projected."
    instruction_text_1 = "Press the 'Q' key on your keyboard to save and finish."
    instruction_text_2 = "Click 'Back' to return to the placement step to make adjustments."

    cv2.putText(canvas, title_text, (text_start_x, ui_components.Y_TITLE), cv2.FONT_HERSHEY_SIMPLEX, 0.8, ui_components.COLOR_TEXT, 2, cv2.LINE_AA)
    cv2.putText(canvas, status_text, (text_start_x, ui_components.Y_STATUS), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ui_components.COLOR_TEXT, 1, cv2.LINE_AA)
    cv2.putText(canvas, instruction_text_1, (text_start_x, ui_components.Y_INSTRUCTION_1), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1, cv2.LINE_AA)
    cv2.putText(canvas, instruction_text_2, (text_start_x, ui_components.Y_INSTRUCTION_2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1, cv2.LINE_AA)

# --- Grid Calculation functions (unchanged) ---
def _order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s, diff = pts.sum(axis=1), np.diff(pts, axis=1)
    rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]
    rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)]
    return rect

def _draw_grid_on_rectangle(frame, corners):
    if corners is None or len(corners) != 4: return
    src_pts = _order_points(corners)
    dst_w, dst_h = 1200, 1300
    dst_pts = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(dst_pts, src_pts)
    grid_points_dst = []
    x_step, y_step = dst_w / GRID_COLS, dst_h / GRID_ROWS
    for i in range(GRID_ROWS):
        for j in range(GRID_COLS):
            grid_points_dst.append([(j + 0.5) * x_step, (i + 0.5) * y_step])
    grid_points_dst = np.array([grid_points_dst], dtype="float32")
    if grid_points_dst.size > 0:
        grid_points_src = cv2.perspectiveTransform(grid_points_dst, M)
        for pt in grid_points_src[0]:
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 4, COLOR_GRID_POINT, -1)
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 4, (255,255,255), 1)
    cv2.drawContours(frame, [np.int32(corners)], 0, COLOR_RECTANGLE_BORDER, 1)