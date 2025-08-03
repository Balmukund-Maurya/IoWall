# Import required libraries
import rumps  # For creating macOS menu bar applications
import requests  # For making HTTP requests (downloading images)
import os  # For file and path operations
import subprocess  # To run AppleScript for setting wallpaper
import tempfile  # To store images in temporary directory
from datetime import datetime  # For timestamping saved images
import socket  # (Not used directly; can be removed)
import threading  # To run tasks asynchronously without blocking UI
import logging  # For logging errors and events
import AppKit  # For accessing macOS screen info (resolution)
import imghdr  # To verify image type (JPEG)

# Configure logging format and level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Main Application Class
class IoWall(rumps.App):
    def __init__(self):
        # Set app icon and name
        icon_path = os.path.join(os.path.dirname(__file__), "IoWall_icon_B.icns")
        super(IoWall, self).__init__("IoWall", icon=icon_path, quit_button="Quit")

        # Get current screen resolution and initialize state
        self.current_resolution = self.get_screen_resolution()
        self.last_image = None  # Stores path to last downloaded image
        self.last_category = "Random"  # Default category

        # Menu items for the menu bar app
        self.menu = [
            "Change Wallpaper",
            {
                "Categories": [  # Submenu for categories
                    "Nature",
                    "City",
                    "Tech",
                    "Abstract",
                    "Random"
                ]
            },
            None,
            "Set 4K Resolution",
            "Save Wallpaper",
            "Clear Cache"
        ]

        # Clean old temp images and set initial wallpaper
        self.clean_temp_files()
        self.set_wallpaper_from_category("Random")

    # Detect screen resolution using AppKit
    def get_screen_resolution(self):
        try:
            screen = AppKit.NSScreen.mainScreen()
            if screen is None:
                raise ValueError("No main screen found.")
            frame = screen.frame()
            width, height = int(frame.size.width), int(frame.size.height)
            return (width, height)
        except Exception as e:
            logging.warning(f"Screen resolution fallback: {e}")
            return (1920, 1080)  # Default fallback

    # Check for internet connectivity
    def is_internet_connected(self):
        try:
            requests.get("https://www.google.com", timeout=3)
            return True
        except:
            return False

    # Construct URL to fetch image based on category
    def get_image_url(self, category):
        base_url = "https://picsum.photos"
        width, height = self.current_resolution

        if category == "Random":
            return f"{base_url}/{width}/{height}"
        elif category == "Abstract":
            return f"{base_url}/seed/abstract/{width}/{height}?blur=2"
        else:
            return f"{base_url}/seed/{category.lower()}/{width}/{height}"

    # Download image and validate it
    def download_wallpaper(self, url):
        if not self.is_internet_connected():
            self.safe_alert("No Internet", "You're not connected to the internet.\nPlease check your connection and try again.")
            return None

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Save image to temp file
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix="IoWall_")
            tmp_file.write(response.content)
            tmp_file.close()

            # Validate file is a JPEG
            if imghdr.what(tmp_file.name) != 'jpeg':
                os.remove(tmp_file.name)
                raise ValueError("Downloaded file is not a valid JPEG image.")

            self.last_image = tmp_file.name
            return tmp_file.name

        except requests.exceptions.RequestException as e:
            logging.error(f"Wallpaper download failed: {e}")
            self.safe_alert("Download Error", f"Failed to download wallpaper.\n{str(e)}")
            return None
        except Exception as e:
            logging.error(f"Image validation error: {e}")
            self.safe_alert("Download Error", f"Invalid image received.\n{str(e)}")
            return None

    # Set desktop wallpaper using AppleScript
    def set_wallpaper(self, image_path):
        try:
            subprocess.run([
                "osascript", "-e",
                f'tell application "Finder" to set desktop picture to POSIX file "{image_path}"'
            ], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to set wallpaper: {e}")
            self.safe_alert("Set Wallpaper Error", f"Could not set wallpaper:\n{str(e)}")

    # Async task to change wallpaper based on category
    def set_wallpaper_from_category(self, category):
        def worker():
            try:
                self.set_loading_state(True, f"Loading {category}...")
                self.last_category = category
                url = self.get_image_url(category)
                image_path = self.download_wallpaper(url)
                if image_path:
                    self.set_wallpaper(image_path)
            except Exception as e:
                logging.error(f"Error changing wallpaper: {e}")
                self.safe_alert("Category Error", f"Failed to change wallpaper:\n{str(e)}")
            finally:
                self.set_loading_state(False)

        threading.Thread(target=worker, daemon=True).start()

    # Toggle loading state in the menu
    def set_loading_state(self, is_loading, message=""):
        item = self.menu["Change Wallpaper"]
        if is_loading:
            item.title = message or "Loading..."
            item.set_callback(None)
        else:
            item.title = "Change Wallpaper"
            item.set_callback(self.change_random_wallpaper)

    # Delete leftover temp files from previous sessions
    def clean_temp_files(self):
        temp_dir = tempfile.gettempdir()
        for filename in os.listdir(temp_dir):
            if filename.startswith("IoWall_") and filename.endswith(".jpg"):
                try:
                    os.remove(os.path.join(temp_dir, filename))
                except Exception as e:
                    logging.warning(f"Failed to remove temp file {filename}: {e}")

    # Show alert message in a safe async way
    def safe_alert(self, title, message):
        def show_alert(_):
            rumps.alert(title, message)

        rumps.Timer(show_alert, 0.1).start()

    # Show macOS notification in safe async way
    def safe_notify(self, title, subtitle, message):
        def show_notification(_):
            rumps.notification(title, subtitle, message)

        rumps.Timer(show_notification, 0.1).start()

    # Menu callback: Set resolution to 4K
    @rumps.clicked("Set 4K Resolution")
    def set_4k_resolution(self, _):
        self.current_resolution = (3840, 2160)
        self.safe_notify("Resolution Set", "", "Resolution changed to 4K (3840x2160)")

    # Menu callback: Change to random wallpaper
    @rumps.clicked("Change Wallpaper")
    def change_random_wallpaper(self, _):
        self.set_wallpaper_from_category("Random")

    # Dummy function to allow submenu registration
    @rumps.clicked("Categories")
    def dummy(self, _): pass

    # Menu callbacks: Set wallpapers from categories
    @rumps.clicked("Categories", "Nature")
    def set_nature_wallpaper(self, _):
        self.set_wallpaper_from_category("Nature")

    @rumps.clicked("Categories", "City")
    def set_city_wallpaper(self, _):
        self.set_wallpaper_from_category("City")

    @rumps.clicked("Categories", "Tech")
    def set_tech_wallpaper(self, _):
        self.set_wallpaper_from_category("Tech")

    @rumps.clicked("Categories", "Abstract")
    def set_abstract_wallpaper(self, _):
        self.set_wallpaper_from_category("Abstract")

    @rumps.clicked("Categories", "Random")
    def set_random_wallpaper(self, _):
        self.set_wallpaper_from_category("Random")

    # Menu callback: Save current wallpaper to Pictures/IoWall
    @rumps.clicked("Save Wallpaper")
    def save_wallpaper(self, _):
        try:
            if not self.last_image or not os.path.exists(self.last_image):
                self.safe_alert("Save Failed", "No wallpaper has been set yet.")
                return

            save_dir = os.path.expanduser("~/Pictures/IoWall/")
            os.makedirs(save_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.last_category}_{timestamp}.jpg"
            destination = os.path.join(save_dir, filename)

            with open(self.last_image, 'rb') as src, open(destination, 'wb') as dst:
                dst.write(src.read())

            self.safe_notify("Wallpaper Saved", "", f"Saved to: {destination}")
        except Exception as e:
            logging.error(f"Save failed: {e}")
            self.safe_alert("Save Error", f"Failed to save wallpaper:\n{str(e)}")

    # Menu callback: Clear cached temp wallpaper
    @rumps.clicked("Clear Cache")
    def clear_cache(self, _):
        try:
            if self.last_image and os.path.exists(self.last_image):
                os.remove(self.last_image)
                self.last_image = None
                self.safe_notify("Cache Cleared", "", "Temporary wallpaper file deleted.")
            else:
                self.safe_alert("Clear Cache", "No temporary cache file found to delete.")
        except Exception as e:
            logging.error(f"Clear cache error: {e}")
            self.safe_alert("Clear Cache Error", f"Could not clear cache:\n{str(e)}")


# Run the app
if __name__ == "__main__":
    IoWall().run()
