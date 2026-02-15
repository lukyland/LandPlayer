import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import pygame
import os
import sys
from mutagen.mp3 import MP3
from PIL import Image, ImageTk
import io
import time
import random
import json
import platform

# Initialize pygame mixer for audio
pygame.mixer.init()

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def set_windows_appid():
    """Set Windows AppUserModelID to make taskbar icon work"""
    if platform.system() == 'Windows':
        try:
            import ctypes
            myappid = 'lukyland.landplayer.audioplayer.1.0'  # Arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            print("Windows AppUserModelID set")
        except Exception as e:
            print(f"Could not set AppUserModelID: {e}")

class MediaPlayer:
    def __init__(self, root):
        self.root = root
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.audio_length = 0
        self.update_job = None
        self.is_seeking = False
        self.start_time = 0
        self.seek_position = 0
        self.pause_button = None
        self.loop_button = None
        self.screen_button = None
        self.loop_mode = "none"  # "none", "media", or "queue"
        self.is_fullscreen = False
        self.queue = []
        self.current_queue_index = -1
        self.queue_window = None
        self.drag_start_index = None
        self.volume = 100  # Default volume at 100%

        # Set window icon
        self.set_window_icon(self.root)

        # Bind keyboard shortcuts
        self.root.bind('<space>', lambda e: self.toggle_pause())
        self.root.bind('<Control-Right>', lambda e: self.next_track())
        self.root.bind('<Control-Left>', lambda e: self.previous_track())
        self.root.bind('<F11>', lambda e: self.toggle_fullscreen())
        self.root.bind('<Left>', lambda e: self.seek_backward())
        self.root.bind('<Right>', lambda e: self.seek_forward())

    def set_window_icon(self, window):
        """Set the window icon if landplayer.ico exists"""
        try:
            # Use resource_path to find icon in both dev and EXE
            icon_path = resource_path('landplayer.ico')
            if os.path.exists(icon_path):
                window.iconbitmap(icon_path)
                # Also try to set it using PhotoImage for better compatibility
                try:
                    img = Image.open(icon_path)
                    photo = ImageTk.PhotoImage(img)
                    window.iconphoto(True, photo)
                except:
                    pass
                print(f"Icon loaded: {icon_path}")
            else:
                print(f"Icon file not found: {icon_path}")
        except Exception as e:
            print(f"Could not load icon: {e}")

    def set_volume(self, value):
        """Set the volume (0-100%)"""
        self.volume = float(value)
        # pygame.mixer.music.set_volume takes 0.0 to 1.0
        pygame.mixer.music.set_volume(self.volume / 100.0)
        volume_label.config(text=f"{int(self.volume)}%")

    def seek_backward(self):
        """Seek 5 seconds backward"""
        if self.current_file and self.audio_length > 0:
            current_position = progress_bar['value']
            new_position = max(0, current_position - 5)
            self.seek_audio(new_position)
            print(f"Seeked backward to: {self.format_time(new_position)}")

    def seek_forward(self):
        """Seek 5 seconds forward"""
        if self.current_file and self.audio_length > 0:
            current_position = progress_bar['value']
            new_position = min(self.audio_length, current_position + 5)
            self.seek_audio(new_position)
            print(f"Seeked forward to: {self.format_time(new_position)}")

    def toggle_loop_mode(self):
        """Toggle through loop modes: none -> media -> queue -> none"""
        if self.loop_mode == "none":
            self.loop_mode = "media"
            self.loop_button.config(text="Loop: Queue")
            print("Loop mode: Media (looping current media)")
        elif self.loop_mode == "media":
            self.loop_mode = "queue"
            self.loop_button.config(text="Loop: None")
            print("Loop mode: Queue (looping entire queue)")
        else:  # queue
            self.loop_mode = "none"
            self.loop_button.config(text="Loop: Media")
            print("Loop mode: None (no looping)")

    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode"""
        if self.is_fullscreen:
            # Exit fullscreen
            self.root.attributes('-fullscreen', False)
            self.is_fullscreen = False
            self.screen_button.config(text="Screen: Full")
            print("Switched to windowed mode")
        else:
            # Enter fullscreen
            self.root.attributes('-fullscreen', True)
            self.is_fullscreen = True
            self.screen_button.config(text="Screen: Window")
            print("Switched to fullscreen mode")

    def shuffle_queue(self):
        """Shuffle the queue randomly"""
        if len(self.queue) <= 1:
            print("Queue has only one or no items, nothing to shuffle")
            return

        # Save the currently playing file
        current_file = self.current_file if self.current_queue_index >= 0 else None

        # Shuffle the queue
        random.shuffle(self.queue)

        # Find the new index of the currently playing file
        if current_file:
            try:
                self.current_queue_index = self.queue.index(current_file)
            except ValueError:
                self.current_queue_index = 0

        print(f"Queue shuffled! ({len(self.queue)} items)")
        self.update_queue_window()

    def save_queue(self):
        """Save the current queue to a file"""
        if not self.queue:
            print("Queue is empty, nothing to save")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Queue",
            defaultextension=".lukyland",
            filetypes=[("lukyland", "*.lukyland"), ("All Files", "*.*")]
        )

        if file_path:
            try:
                queue_data = {
                    "queue": self.queue,
                    "current_index": self.current_queue_index
                }
                with open(file_path, 'w') as f:
                    json.dump(queue_data, f, indent=2)
                print(f"Queue saved to: {file_path}")
                print(f"Saved {len(self.queue)} items")
            except Exception as e:
                print(f"Error saving queue: {e}")

    def load_queue(self):
        """Load a queue from a file"""
        file_path = filedialog.askopenfilename(
            title="Load Queue",
            filetypes=[("lukyland", "*.lukyland"), ("All Files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'r') as f:
                    queue_data = json.load(f)

                # Load the queue
                loaded_queue = queue_data.get("queue", [])

                # Filter out files that don't exist and video files
                valid_files = []
                invalid_count = 0
                video_count = 0
                for file in loaded_queue:
                    if os.path.exists(file):
                        if not self.is_video_file(file):
                            valid_files.append(file)
                        else:
                            video_count += 1
                    else:
                        invalid_count += 1

                if not valid_files:
                    print("No valid audio files found in queue")
                    return

                # Stop current playback if any
                if self.is_playing or self.is_paused:
                    pygame.mixer.music.stop()
                    self.is_playing = False
                    self.is_paused = False

                # Set the new queue
                self.queue = valid_files
                self.current_queue_index = 0

                print(f"Queue loaded from: {file_path}")
                print(f"Loaded {len(valid_files)} audio files")
                if invalid_count > 0:
                    print(f"Warning: {invalid_count} files not found and were skipped")
                if video_count > 0:
                    print(f"Warning: {video_count} video files skipped (audio only)")

                # Start playing the first track
                if self.queue:
                    self.play_media(self.queue[0])

                self.update_queue_window()

            except Exception as e:
                print(f"Error loading queue: {e}")

    def on_drag_start(self, event):
        """Handle start of drag operation"""
        # Get the index of the item being dragged
        self.drag_start_index = self.queue_listbox.nearest(event.y)

    def on_drag_motion(self, event):
        """Handle drag motion to highlight drop position"""
        # Get current position
        current_index = self.queue_listbox.nearest(event.y)

        # Clear previous selection
        self.queue_listbox.selection_clear(0, tk.END)

        # Highlight current position
        if 0 <= current_index < len(self.queue):
            self.queue_listbox.selection_set(current_index)

    def on_drag_release(self, event):
        """Handle end of drag operation and reorder queue"""
        if self.drag_start_index is None:
            return

        # Get the drop index
        drop_index = self.queue_listbox.nearest(event.y)

        # Make sure indices are valid
        if (0 <= self.drag_start_index < len(self.queue) and 
            0 <= drop_index < len(self.queue) and 
            self.drag_start_index != drop_index):

            # Get the item being moved
            item = self.queue[self.drag_start_index]

            # Remove from old position
            self.queue.pop(self.drag_start_index)

            # Insert at new position
            self.queue.insert(drop_index, item)

            # Update current_queue_index if needed
            if self.drag_start_index == self.current_queue_index:
                # Currently playing item was moved
                self.current_queue_index = drop_index
            elif self.drag_start_index < self.current_queue_index <= drop_index:
                # Item moved from before to after current
                self.current_queue_index -= 1
            elif drop_index <= self.current_queue_index < self.drag_start_index:
                # Item moved from after to before current
                self.current_queue_index += 1

            print(f"Moved '{os.path.basename(item)}' from position {self.drag_start_index} to {drop_index}")

            # Update display
            self.update_queue_window()

        # Reset drag start index
        self.drag_start_index = None

    def on_queue_double_click(self, event):
        """Handle double-click on queue item to skip to that track"""
        # Get the index of the clicked item
        click_index = self.queue_listbox.nearest(event.y)

        if 0 <= click_index < len(self.queue):
            # Skip to the selected track
            self.current_queue_index = click_index
            selected_file = self.queue[click_index]
            print(f"Skipping to: {os.path.basename(selected_file)}")
            self.play_media(selected_file)
            self.update_queue_window()

    def is_video_file(self, file_path):
        """Check if file is a video format"""
        video_formats = ['.mp4', '.avi', '.mkv', '.mov', '.wmv']
        file_ext = os.path.splitext(file_path)[1].lower()
        return file_ext in video_formats

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Open Audio File",
            filetypes=[
                ("Audio Files", "*.mp3 *.wav *.flac *.aac *.ogg"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            # Check if it's a video file
            if self.is_video_file(file_path):
                messagebox.showwarning("Video Not Supported", 
                    "This is an audio-only player.\nVideo files are not supported.")
                print("Video files not supported (audio only)")
                return

            self.current_file = file_path
            self.queue = [file_path]
            self.current_queue_index = 0
            self.play_media(file_path)
            self.update_queue_window()

    def open_folder(self):
        folder_path = filedialog.askdirectory(title="Open Folder")
        if folder_path:
            # Get all audio files from the folder (no video)
            audio_extensions = ['.mp3', '.wav', '.flac', '.aac', '.ogg']
            self.queue = []

            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file_path)
                    if ext.lower() in audio_extensions:
                        self.queue.append(file_path)

            # Sort queue alphabetically
            self.queue.sort()

            if self.queue:
                self.current_queue_index = 0
                print(f"Loaded {len(self.queue)} audio files from folder")
                print(f"Queue: {[os.path.basename(f) for f in self.queue]}")
                self.play_media(self.queue[0])
                self.update_queue_window()
            else:
                messagebox.showinfo("No Audio Files", "No audio files found in folder.")
                print("No audio files found in folder")

    def add_file_to_queue(self):
        """Add a single file to the end of the queue"""
        file_path = filedialog.askopenfilename(
            title="Add Audio File to Queue",
            filetypes=[
                ("Audio Files", "*.mp3 *.wav *.flac *.aac *.ogg"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            # Check if it's a video file
            if self.is_video_file(file_path):
                messagebox.showwarning("Video Not Supported", 
                    "This is an audio-only player.\nVideo files are not supported.")
                print("Video files not supported (audio only)")
                return

            self.queue.append(file_path)
            print(f"Added to queue: {os.path.basename(file_path)}")

            # If nothing is playing, start playing the added file
            if not self.is_playing and not self.is_paused:
                self.current_queue_index = len(self.queue) - 1
                self.play_media(file_path)

            self.update_queue_window()

    def add_folder_to_queue(self):
        """Add all audio files from a folder to the end of the queue"""
        folder_path = filedialog.askdirectory(title="Add Folder to Queue")
        if folder_path:
            audio_extensions = ['.mp3', '.wav', '.flac', '.aac', '.ogg']
            added_files = []

            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file_path)
                    if ext.lower() in audio_extensions:
                        added_files.append(file_path)

            # Sort files alphabetically
            added_files.sort()

            if added_files:
                # If nothing is playing, mark the first file to play
                start_playing = not self.is_playing and not self.is_paused and len(self.queue) == 0

                # Add to queue
                self.queue.extend(added_files)

                print(f"Added {len(added_files)} audio files to queue from folder")

                # If nothing was playing, start playing the first added file
                if start_playing:
                    self.current_queue_index = 0
                    self.play_media(self.queue[0])

                self.update_queue_window()
            else:
                messagebox.showinfo("No Audio Files", "No audio files found in folder.")
                print("No audio files found in folder")

    def show_queue_window(self):
        """Open or focus the queue window"""
        if self.queue_window is not None and tk.Toplevel.winfo_exists(self.queue_window):
            # Window already exists, just bring it to front
            self.queue_window.lift()
            self.queue_window.focus()
        else:
            # Create new queue window
            self.queue_window = tk.Toplevel(self.root)
            self.queue_window.title("Queue")
            self.queue_window.geometry("500x400")

            # Set icon for queue window
            self.set_window_icon(self.queue_window)

            # Create frame for queue list
            queue_frame = tk.Frame(self.queue_window)
            queue_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Add scrollbar
            scrollbar = tk.Scrollbar(queue_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Create listbox for queue items
            self.queue_listbox = tk.Listbox(queue_frame, yscrollcommand=scrollbar.set, font=("Arial", 10))
            self.queue_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            scrollbar.config(command=self.queue_listbox.yview)

            # Bind drag and drop events
            self.queue_listbox.bind('<Button-1>', self.on_drag_start)
            self.queue_listbox.bind('<B1-Motion>', self.on_drag_motion)
            self.queue_listbox.bind('<ButtonRelease-1>', self.on_drag_release)

            # Bind double-click event
            self.queue_listbox.bind('<Double-Button-1>', self.on_queue_double_click)

            # Populate the queue
            self.update_queue_window()

    def update_queue_window(self):
        """Update the queue window with current queue"""
        if self.queue_window is not None and tk.Toplevel.winfo_exists(self.queue_window):
            # Clear current list
            self.queue_listbox.delete(0, tk.END)

            # Add all items in queue
            for i, file_path in enumerate(self.queue):
                filename = os.path.basename(file_path)
                # Mark currently playing track
                if i == self.current_queue_index:
                    display_text = f"► {filename}"
                    self.queue_listbox.insert(tk.END, display_text)
                    # Highlight currently playing
                    self.queue_listbox.itemconfig(i, bg='lightblue')
                else:
                    self.queue_listbox.insert(tk.END, filename)

    def play_next_in_queue(self):
        """Play the next file in the queue"""
        if self.current_queue_index < len(self.queue) - 1:
            self.current_queue_index += 1
            next_file = self.queue[self.current_queue_index]
            print(f"Playing next in queue: {os.path.basename(next_file)}")
            self.play_media(next_file)
            self.update_queue_window()
        else:
            # Reached end of queue
            if self.loop_mode == "queue":
                # Loop back to start of queue
                print("Looping queue from beginning")
                self.current_queue_index = 0
                self.play_media(self.queue[0])
                self.update_queue_window()
            else:
                print("End of queue")
                self.is_playing = False
                self.is_paused = False
                if self.pause_button:
                    self.pause_button.config(text="Pause")

    def play_previous_in_queue(self):
        """Play the previous file in the queue or restart current"""
        # Get current playback time
        current_time = progress_bar['value']

        # If less than 3 seconds, go to previous track
        if current_time < 3 and self.current_queue_index > 0:
            self.current_queue_index -= 1
            prev_file = self.queue[self.current_queue_index]
            print(f"Playing previous in queue: {os.path.basename(prev_file)}")
            self.play_media(prev_file)
            self.update_queue_window()
        else:
            # Restart current track
            print("Restarting current track")
            if self.current_file:
                self.play_media(self.current_file)

    def next_track(self):
        """Skip to next track in queue"""
        if self.current_queue_index < len(self.queue) - 1:
            self.play_next_in_queue()
        else:
            # At last track
            if self.loop_mode == "queue":
                # Loop back to start
                print("Looping queue from beginning")
                self.current_queue_index = 0
                self.play_media(self.queue[0])
                self.update_queue_window()
            else:
                print("Already at last track")

    def previous_track(self):
        """Go to previous track or restart current"""
        self.play_previous_in_queue()

    def play_media(self, file_path):
        """Play audio file"""
        try:
            # Get audio length
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext == '.mp3':
                audio = MP3(file_path)
                self.audio_length = audio.info.length
            else:
                # For other audio formats
                try:
                    sound = pygame.mixer.Sound(file_path)
                    self.audio_length = sound.get_length()
                except:
                    # If Sound fails, load and estimate
                    pygame.mixer.music.load(file_path)
                    self.audio_length = 0

            # Load and play audio
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()

            # Set volume to current level
            pygame.mixer.music.set_volume(self.volume / 100.0)

            self.is_playing = True
            self.is_paused = False
            self.current_file = file_path

            # Update pause button text
            if self.pause_button:
                self.pause_button.config(text="Pause")

            # Update total time display
            if self.audio_length > 0:
                total_time = self.format_time(self.audio_length)
                time_right.config(text=total_time)
                progress_bar['maximum'] = self.audio_length
            else:
                time_right.config(text="--:--")

            progress_bar['value'] = 0

            # Display audio icon
            self.display_audio_icon(file_path)

            # Start updating progress
            self.start_time = time.time()
            self.seek_position = 0
            self.update_progress()

            print(f"Now playing: {os.path.basename(file_path)}")

        except Exception as e:
            print(f"Error playing file: {e}")
            # Try to play next in queue if there's an error
            if self.current_queue_index < len(self.queue) - 1:
                self.play_next_in_queue()

    def toggle_pause(self):
        """Toggle pause/resume for audio playback"""
        if not self.current_file:
            return

        if self.is_paused:
            # Resume
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.is_playing = True

            # Adjust start_time to account for paused duration
            self.start_time = time.time() - (progress_bar['value'] - self.seek_position)

            # Update button
            self.pause_button.config(text="Pause")

            # Restart progress updates
            self.update_progress()

            print("Resumed")
        else:
            # Pause
            if self.is_playing:
                pygame.mixer.music.pause()
                self.is_paused = True
                self.is_playing = False

                # Update button
                self.pause_button.config(text="Resume")

                print("Paused")

    def display_audio_icon(self, file_path):
        try:
            # Try to extract album art
            from mutagen.id3 import ID3
            audio = ID3(file_path)

            # Look for album art
            for key in audio.keys():
                if key.startswith('APIC'):
                    artwork = audio[key].data
                    img = Image.open(io.BytesIO(artwork))

                    # Resize to fit nicely
                    img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)

                    video_label.config(image=photo, text='')
                    video_label.image = photo
                    return
        except:
            pass

        # If no album art, show a default music icon
        try:
            # Create a simple music note icon
            icon_img = Image.new('RGB', (300, 300), color='black')
            photo = ImageTk.PhotoImage(icon_img)
            video_label.config(image=photo, text="♪ Now Playing ♪", 
                             compound='center', fg='white', 
                             font=('Arial', 24))
            video_label.image = photo
        except Exception as e:
            # Fallback to just text
            video_label.config(image='', text="♪ Now Playing ♪", 
                             fg='white', font=('Arial', 24))

    def update_progress(self):
        if self.is_playing and pygame.mixer.music.get_busy() and not self.is_paused:
            # Calculate elapsed time from start plus any seek offset
            elapsed = (time.time() - self.start_time) + self.seek_position

            # Update progress bar
            if self.audio_length > 0:
                progress_bar['value'] = min(elapsed, self.audio_length)
            else:
                progress_bar['value'] = elapsed

            # Update time label
            current_time = self.format_time(elapsed)
            time_left.config(text=current_time)

            # Schedule next update
            self.update_job = self.root.after(100, self.update_progress)
        elif self.is_playing and not pygame.mixer.music.get_busy() and not self.is_paused:
            # Music has finished
            if self.loop_mode == "media":
                # Loop current media
                print("Looping current media")
                self.play_media(self.current_file)
            else:
                # Play next in queue or loop queue (or stop if loop_mode is "none")
                print("Track finished")
                self.play_next_in_queue()

    def seek_audio(self, position):
        """Seek to a specific position in the audio"""
        if self.current_file and self.audio_length > 0:
            try:
                # Stop current playback
                pygame.mixer.music.stop()

                # Reload and play from new position
                pygame.mixer.music.load(self.current_file)
                pygame.mixer.music.play(start=position)

                # Restore volume
                pygame.mixer.music.set_volume(self.volume / 100.0)

                # Update timing variables
                self.start_time = time.time()
                self.seek_position = position
                self.is_playing = True
                self.is_paused = False

                # Update button
                if self.pause_button:
                    self.pause_button.config(text="Pause")

                # Restart progress updates if needed
                if self.update_job is None:
                    self.update_progress()

                print(f"Seeked to: {self.format_time(position)}")
            except Exception as e:
                print(f"Error seeking: {e}")

    def on_progress_click(self, event):
        """Handle clicks on the progress bar to seek"""
        if self.audio_length > 0:
            # Calculate position based on click
            click_position = event.x
            bar_width = progress_bar.winfo_width()

            # Calculate time position
            new_position = (click_position / bar_width) * self.audio_length
            new_position = max(0, min(new_position, self.audio_length))

            # Update progress bar immediately
            progress_bar['value'] = new_position
            time_left.config(text=self.format_time(new_position))

            # Seek to new position
            self.seek_audio(new_position)

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

# Set Windows AppUserModelID before creating window
set_windows_appid()

# Create the main window
root = tk.Tk()
root.title("LandPlayer - Audio Player")
root.geometry("800x600")

# Create player instance
player = MediaPlayer(root)

# Create menu bar
menubar = tk.Menu(root)
root.config(menu=menubar)

# Create File menu
file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)

# Add menu items to File menu
file_menu.add_command(label="Open File", command=player.open_file)
file_menu.add_command(label="Open Folder", command=player.open_folder)
file_menu.add_separator()
file_menu.add_command(label="Add File", command=player.add_file_to_queue)
file_menu.add_command(label="Add Folder", command=player.add_folder_to_queue)

# Create Queue menu
queue_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Queue", menu=queue_menu)
queue_menu.add_command(label="Show Queue", command=player.show_queue_window)
queue_menu.add_command(label="Shuffle", command=player.shuffle_queue)
queue_menu.add_separator()
queue_menu.add_command(label="Save Queue", command=player.save_queue)
queue_menu.add_command(label="Load Queue", command=player.load_queue)

# Create black content area
content_area = tk.Frame(root, bg="black")
content_area.pack(fill=tk.BOTH, expand=True)

# Create label for video display
video_label = tk.Label(content_area, bg="black")
video_label.pack(fill=tk.BOTH, expand=True)

# Create bottom control panel
bottom_frame = tk.Frame(root)
bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

# Progress bar with time labels on same line
progress_frame = tk.Frame(bottom_frame)
progress_frame.pack(fill=tk.X, pady=(0, 5))

time_left = tk.Label(progress_frame, text="00:00")
time_left.pack(side=tk.LEFT, padx=(0, 5))

# Progress bar
progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode='determinate')
progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

# Bind click event to progress bar for seeking
progress_bar.bind('<Button-1>', player.on_progress_click)

time_right = tk.Label(progress_frame, text="/")
time_right.pack(side=tk.LEFT, padx=(5, 0))

# Create frame for buttons and volume
controls_frame = tk.Frame(bottom_frame)
controls_frame.pack(fill=tk.X)

# Button controls frame (left side)
button_frame = tk.Frame(controls_frame)
button_frame.pack(side=tk.LEFT, expand=True)

# Create control buttons
for i in range(1, 6):
    if i == 1:
        # Button 1 is the Loop button
        btn = tk.Button(button_frame, text="Loop: Media", width=10, command=player.toggle_loop_mode)
        player.loop_button = btn
    elif i == 2:
        # Button 2 is the Back button
        btn = tk.Button(button_frame, text="Back", width=6, command=player.previous_track)
    elif i == 3:
        # Button 3 is the pause/resume button
        btn = tk.Button(button_frame, text="Pause", width=8, command=player.toggle_pause)
        player.pause_button = btn
    elif i == 4:
        # Button 4 is the Next button
        btn = tk.Button(button_frame, text="Next", width=6, command=player.next_track)
    elif i == 5:
        # Button 5 is the Screen toggle button
        btn = tk.Button(button_frame, text="Screen: Full", width=11, command=player.toggle_fullscreen)
        player.screen_button = btn
    btn.pack(side=tk.LEFT, padx=5)

# Volume control frame (right side)
volume_frame = tk.Frame(controls_frame)
volume_frame.pack(side=tk.RIGHT, padx=(20, 0))

tk.Label(volume_frame, text="Volume:").pack(side=tk.LEFT, padx=(0, 5))

# Volume slider (0-100%)
volume_slider = tk.Scale(volume_frame, from_=0, to=100, orient=tk.HORIZONTAL, 
                         command=player.set_volume, length=150, showvalue=0)
volume_slider.set(100)  # Default to 100%
volume_slider.pack(side=tk.LEFT)

# Volume percentage label
volume_label = tk.Label(volume_frame, text="100%", width=5)
volume_label.pack(side=tk.LEFT, padx=(5, 0))

# Run the application
root.mainloop()
