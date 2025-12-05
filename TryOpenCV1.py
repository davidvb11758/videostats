import cv2
import numpy as np

# Real-world volleyball court coordinates (meters)
# Define court corners in order: BL, BR, TR, TL
court_coords = np.array([
    [0, 0],
    [9, 0],
    [9, 18],
    [0, 18]
], dtype=np.float32)

# Store clicked pixel points
pixel_points = []
homography_matrix = None

# Mouse callback
def click_event(event, x, y, flags, param):
    global pixel_points, homography_matrix

    if event == cv2.EVENT_LBUTTONDOWN:
        if homography_matrix is None:
            pixel_points.append([x, y])
            print(f"Corner point registered: {len(pixel_points)}/4  -> ({x}, {y})")

            # Draw a dot
            cv2.circle(img, (x, y), 5, (0, 0, 255), -1)
            cv2.imshow("Court", img)

            # Once 4 points selected → compute homography
            if len(pixel_points) == 4:
                src = np.array(pixel_points, dtype=np.float32)
                homography_matrix, _ = cv2.findHomography(src, court_coords)
                print("\nHomography Calibration Complete ✓")
                print("Now click anywhere to get real court coordinates.")
                print("-------------------------------------------------\n")

        else:
            # Convert pixel → court position
            px = np.array([x, y, 1]).reshape(3, 1)
            mapped = homography_matrix @ px
            mapped /= mapped[2]
            cx, cy = mapped[0][0], mapped[1][0]

            print(f"Clicked Pixel: ({x}, {y}) → Court (m): ({cx:.2f}, {cy:.2f})")

# Load your court image (change filename)
img = cv2.imread("volleyball_court.png")
clone = img.copy()

cv2.imshow("Court", img)
cv2.setMouseCallback("Court", click_event)
cv2.waitKey(0)
cv2.destroyAllWindows()
