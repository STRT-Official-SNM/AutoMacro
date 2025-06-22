import os
import time
import threading
import tkinter as tk  # Import the GUI library
import numpy as np
from PIL import Image
import pyscreenshot as ImageGrab
from pynput import mouse, keyboard
from skimage.metrics import structural_similarity as ssim

REPLAY_START_DELAY_SECONDS = 4
VALIDATION_AREA_SIZE = (200, 100) 
SIMILARITY_THRESHOLD = 0.85
WAIT_TIMEOUT_SECONDS = 20

recorded_actions = []
recording = False
last_time = 0
mouse_controller = mouse.Controller()
keyboard_controller = keyboard.Controller()
def get_time_delta():
    global last_time
    current_time = time.time()
    delta = current_time - last_time
    last_time = current_time
    return delta
def create_screenshots_dir():
    if not os.path.exists('screenshots'):
        os.makedirs('screenshots')
def compare_images(img_path1, img2_pil):
    try:
        img1_pil = Image.open(img_path1).convert('L')
        img2_pil = img2_pil.convert('L')
        if img1_pil.size != img2_pil.size:
            img2_pil = img2_pil.resize(img1_pil.size)
        img1_np = np.array(img1_pil)
        img2_np = np.array(img2_pil)
        similarity_index = ssim(img1_np, img2_np)
        return similarity_index
    except FileNotFoundError:
        print(f"ERROR: Screenshot file for comparison not found at {img_path1}")
        return 0
    except Exception as e:
        print(f"An error occurred during image comparison: {e}")
        return 0
def wait_for_region_to_match(screenshot_path, bbox):
    print(f"VALIDATING: Waiting for screen region {bbox} to match '{os.path.basename(screenshot_path)}'...")
    start_time = time.time()
    while time.time() - start_time < WAIT_TIMEOUT_SECONDS:
        try:
            current_screenshot = ImageGrab.grab(bbox=bbox)
            similarity = compare_images(screenshot_path, current_screenshot)
            print(f"  -> Similarity: {similarity:.2f} (Threshold: {SIMILARITY_THRESHOLD})")
            if similarity > SIMILARITY_THRESHOLD:
                print("  ✅ Match successful! Proceeding...")
                return True
        except Exception as e:
            print(f"  -> Warning: Could not grab screenshot ({e}). Retrying...")
        time.sleep(1)
    print(f"  ❌ TIMEOUT: Screen region did not match after {WAIT_TIMEOUT_SECONDS} seconds.")
    return False
# --- Recording Functions (Listeners) ---
def on_move(x, y):
    if recording:
        recorded_actions.append({'type': 'move', 'pos': (x, y), 'time': get_time_delta()})
def on_click(x, y, button, pressed):
    if recording:
        action_name = 'press' if pressed else 'release'
        action = {'type': 'click', 'pos': (x, y), 'button': button, 'action': action_name, 'time': get_time_delta()}
        if pressed:
            bbox = (x, y, x + VALIDATION_AREA_SIZE[0], y + VALIDATION_AREA_SIZE[1])
            timestamp = int(time.time() * 1000)
            screenshot_filename = f'screenshots/pre_click_{timestamp}.png'
            try:
                pre_action_screenshot = ImageGrab.grab(bbox=bbox)
                pre_action_screenshot.save(screenshot_filename)
                action['validation_screenshot'] = screenshot_filename
                action['validation_bbox'] = bbox
                print(f"📸 Captured validation screenshot: {screenshot_filename}")
            except Exception as e:
                print(f"⚠️ Could not capture validation screenshot: {e}")
        recorded_actions.append(action)
def on_scroll(x, y, dx, dy):
    if recording:
        recorded_actions.append({'type': 'scroll', 'scroll': (dx, dy), 'time': get_time_delta()})
def on_key_press(key):
    if recording:
        recorded_actions.append({'type': 'key_press', 'key': key, 'time': get_time_delta()})
def on_key_release(key):
    if recording:
        recorded_actions.append({'type': 'key_release', 'key': key, 'time': get_time_delta()})
# --- Replay Function ---
def replay_actions():
    if not recorded_actions:
        print("No actions were recorded.")
        return
    print(f"\n--- ▶️ REPLAY WILL START IN {REPLAY_START_DELAY_SECONDS} SECONDS ---")
    print("Switch to the target window now!")
    time.sleep(REPLAY_START_DELAY_SECONDS)
    initial_pause = recorded_actions[0]['time']
    print(f"Initial pause: {initial_pause:.2f} seconds")
    time.sleep(initial_pause)
    for i, action in enumerate(recorded_actions[1:]):
        time.sleep(action['time'])
        if action.get('validation_screenshot'):
            was_successful = wait_for_region_to_match(action['validation_screenshot'], action['validation_bbox'])
            if not was_successful:
                print("\n--- ⏹️ REPLAY ABORTED DUE TO VALIDATION FAILURE ---")
                return
        action_type = action['type']
        if action_type == 'move':
            mouse_controller.position = action['pos']
        elif action_type == 'click':
            if action['action'] == 'press':
                mouse_controller.press(action['button'])
            else:
                mouse_controller.release(action['button'])
        elif action_type == 'scroll':
            mouse_controller.scroll(action['scroll'][0], action['scroll'][1])
        elif action_type == 'key_press':
            keyboard_controller.press(action['key'])
        elif action_type == 'key_release':
            keyboard_controller.release(action['key'])
    print("\n--- ✅ REPLAY FINISHED SUCCESSFULLY ---")


# --- GUI Creation and Control ---

def create_control_window():
    """Creates a floating, 'always on top' window with a stop button."""
    
    # This function is called by the button when it's clicked
    def stop_recording_callback():
        global recording
        recording = False
        print("\n--- ⏹️ RECORDING STOPPED BY USER ---")
        root.destroy() # Close the GUI window

    root = tk.Tk()
    root.title("Recorder")
    
    # Make the window borderless and always on top
    root.overrideredirect(True)
    root.wm_attributes("-topmost", 1)
    
    # Get screen dimensions to position the window
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = 150
    window_height = 50
    # Position in the top-right corner with a 20px margin
    x_pos = screen_width - window_width - 20
    y_pos = 20
    root.geometry(f'{window_width}x{window_height}+{x_pos}+{y_pos}')
    
    # Style the window and button
    root.config(bg='black')
    stop_button = tk.Button(
        root, 
        text="Stop Recording", 
        command=stop_recording_callback,
        bg='#FF4500', # Red-orange color
        fg='white',
        font=('Arial', 10, 'bold'),
        relief='raised',
        borderwidth=2
    )
    stop_button.pack(expand=True, fill='both', padx=10, pady=10)
    
    return root

# --- Main Execution ---

if __name__ == "__main__":
    create_screenshots_dir()
    
    # Setup the pynput listeners in background threads
    mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
    keyboard_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)

    mouse_listener.start()
    keyboard_listener.start()

    print("Recording will start in 3 seconds...")
    time.sleep(3)
    
    recording = True
    last_time = time.time()
    print("--- ⏺️ RECORDING STARTED ---")
    
    # Create and display the GUI control window
    control_window = create_control_window()
    
    # --- Main Control Loop ---
    # This loop keeps the script alive while recording is active
    # and also keeps the GUI responsive.
    while recording:
        # Process any pending GUI events (like button clicks)
        control_window.update()
        control_window.update_idletasks()
        # Sleep for a short time to prevent this loop from using 100% CPU
        time.sleep(0.1)

    # --- After Recording Stops ---
    # Stop the pynput listeners now that the loop has ended
    mouse_listener.stop()
    keyboard_listener.stop()
    
    # Replay all the recorded actions
    replay_actions()
