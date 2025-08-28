# sample_calibrator/__config__.py

# --- Real-World Distances ---
# Define the physical distances between your calibration points in your chosen units (e.g., mm).
DISTANCE_P0_P1 = 142.408
DISTANCE_P1_P2 = 142.408
DISTANCE_P2_P0 = 142.408

# --- UI and Display Settings ---
POINT_COLOR = (0, 0, 255)       # BGR color for points (Red)
LINE_COLOR = (255, 255, 0)      # BGR color for lines (Cyan)
TEXT_COLOR = (0, 255, 255)      # BGR color for distance text (Yellow)
POINT_RADIUS = 7
RECTANGLE_COLOR = (255, 0, 255) # BGR color for the rectangle (Magenta)

# --- Measurement View Settings ---
UNDISTORTED_VIEW_SIZE = (1000, 800) # (width, height) for the corrected view window

# Grid will adapt based on zoom level. Format: (zoom_threshold, grid_spacing_mm)
GRID_ZOOM_LEVELS = [
    (6.0, 1),   # If zoom > 6.0x, use 1mm grid
    (2.5, 5),   # If zoom > 2.5x, use 5mm grid
    (0.0, 10),  # Default 10mm grid
]
GRID_COLOR_MAJOR = (100, 100, 100)
GRID_COLOR_MINOR = (60, 60, 60)
GRID_THICKNESS = 1