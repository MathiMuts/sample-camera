# sample_calibrator/calibration_module.py

import cv2
import numpy as np
import ui_components

COLOR_POINT = (40, 40, 240)

class UIState(ui_components.BaseUIState):
    def __init__(self, frame_width, frame_height):
        super().__init__(frame_width, frame_height)
        self.points = []
        self.confirmed = False
        self.hover_target = None
        # Button positions are now fixed and can be pre-calculated
        total_width = frame_width + ui_components.SIDEBAR_WIDTH
        self.next_button_rect = (total_width - ui_components.BUTTON_WIDTH - ui_components.PADDING, 
                                 ui_components.PADDING, 
                                 ui_components.BUTTON_WIDTH, 
                                 ui_components.BUTTON_HEIGHT)

    def check_hover(self, x, y):
        self.hover_target = None
        if ui_components.is_point_in_rect(x, y, self.next_button_rect):
            self.hover_target = 'next'

def get_three_points(cap):
    ret, frame = cap.read()
    frame = cv2.flip(frame, -1)
    if not ret: return None

    frame_h, frame_w, _ = frame.shape
    state = UIState(frame_w, frame_h)
    
    window_name = 'Calibration | Step 1 of 3'
    # Use a fixed-size window (no WINDOW_NORMAL flag)
    cv2.namedWindow(window_name) 
    cv2.setMouseCallback(window_name, _mouse_callback, state)

    print("--- Calibration Mode ---")
    print("Press 'f' to toggle fullscreen. Select 3 points.")

    while not state.confirmed:
        ret, frame = cap.read()
        frame = cv2.flip(frame, -1)
        if not ret: break

        # Create the canvas with our fixed layout
        canvas = ui_components.create_application_canvas(frame.shape)

        M = np.array([[state.zoom, 0, -state.pan_offset[0] * state.zoom],
                      [0, state.zoom, -state.pan_offset[1] * state.zoom]])
        view_frame = cv2.warpAffine(frame, M, (frame_w, frame_h))

        # Paste the camera view onto the canvas
        canvas[ui_components.HEADER_HEIGHT:, ui_components.SIDEBAR_WIDTH:] = view_frame
        
        # Draw all UI elements
        _draw_ui(canvas, state, len(state.points))

        # Draw selected points, offsetting for sidebar and header
        for (px, py) in state.points:
            disp_x = int((px - state.pan_offset[0]) * state.zoom) + ui_components.SIDEBAR_WIDTH
            disp_y = int((py - state.pan_offset[1]) * state.zoom) + ui_components.HEADER_HEIGHT
            cv2.circle(canvas, (disp_x, disp_y), 7, COLOR_POINT, -1)
            cv2.circle(canvas, (disp_x, disp_y), 7, ui_components.COLOR_TEXT, 1)

        cv2.imshow(window_name, canvas)

        key = cv2.waitKey(20) & 0xFF
        if key == ord('q'):
            state.points = None; break
        elif key == ord('f'):
            state.is_fullscreen = not state.is_fullscreen
            fs_flag = cv2.WINDOW_FULLSCREEN if state.is_fullscreen else cv2.WINDOW_AUTOSIZE
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, fs_flag)

    cv2.destroyWindow(window_name)
    return state.points if state.confirmed else None

def _mouse_callback(event, x, y, flags, state: UIState):
    is_in_header = y < ui_components.HEADER_HEIGHT
    is_in_sidebar = x < ui_components.SIDEBAR_WIDTH
    
    if is_in_header:
        if event == cv2.EVENT_MOUSEMOVE: state.check_hover(x, y)
        elif event == cv2.EVENT_LBUTTONDOWN:
            if state.hover_target == 'next' and len(state.points) == 3:
                state.confirmed = True
        return
    
    if is_in_sidebar: return

    # Correct coordinates to be relative to the viewport
    corrected_x = x - ui_components.SIDEBAR_WIDTH
    corrected_y = y - ui_components.HEADER_HEIGHT

    point_on_frame = ui_components.handle_view_controls(event, corrected_x, corrected_y, flags, state)

    if event == cv2.EVENT_LBUTTONDOWN and len(state.points) < 3:
        orig_coords = (point_on_frame[0], point_on_frame[1])
        print(f"Added point at: ({orig_coords[0]:.2f}, {orig_coords[1]:.2f})")
        state.points.append(orig_coords)
    elif event == cv2.EVENT_RBUTTONDOWN:
        detection_radius = 15 / state.zoom
        point_to_remove = None
        for p in state.points:
            if np.linalg.norm(np.array(p) - point_on_frame) < detection_radius:
                point_to_remove = p
                break
        if point_to_remove:
            state.points.remove(point_to_remove)
            print(f"Removed point near: ({point_to_remove[0]:.2f}, {point_to_remove[1]:.2f})")

def _draw_ui(canvas, state: UIState, num_points):
    next_enabled = num_points == 3
    color = ui_components.COLOR_BUTTON_HOVER if state.hover_target == 'next' and next_enabled else (ui_components.COLOR_BUTTON if next_enabled else ui_components.COLOR_BUTTON_DISABLED)
    text_color = ui_components.COLOR_TEXT if next_enabled else ui_components.COLOR_TEXT_DISABLED
    ui_components.draw_button(canvas, "Next", state.next_button_rect, color, text_color)
    
    text_start_x = ui_components.SIDEBAR_WIDTH + ui_components.PADDING
    
    title_text = "Step 1: Calibrate Corner Points"
    status_text = f"Points Selected: {num_points}/3"
    instruction_1 = "Click on the three designated corner points on the physical rig."
    instruction_2 = "Zoom: Mouse Wheel | Pan: Middle-Click | Remove Point: Right-Click"
    
    cv2.putText(canvas, title_text, (text_start_x, ui_components.Y_TITLE), cv2.FONT_HERSHEY_SIMPLEX, 0.8, ui_components.COLOR_TEXT, 2, cv2.LINE_AA)
    cv2.putText(canvas, status_text, (text_start_x, ui_components.Y_STATUS), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ui_components.COLOR_TEXT, 1, cv2.LINE_AA)
    cv2.putText(canvas, instruction_1, (text_start_x, ui_components.Y_INSTRUCTION_1), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1, cv2.LINE_AA)
    cv2.putText(canvas, instruction_2, (text_start_x, ui_components.Y_INSTRUCTION_2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1, cv2.LINE_AA)