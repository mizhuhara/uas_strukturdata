import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import os
import pygame
import eyed3
from PIL import Image, ImageTk
import io
import time

# Initialize pygame mixer
pygame.mixer.init()

class SongNode:
    def __init__(self, song, next_node=None, prev_node=None):
        self.song = song
        self.next = next_node
        self.prev = prev_node

class PlaylistLinkedList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.length = 0
    
    def append(self, song):
        new_node = SongNode(song)
        if not self.head:
            self.head = new_node
            self.tail = new_node
        else:
            new_node.prev = self.tail
            self.tail.next = new_node
            self.tail = new_node
        self.length += 1
    
    def remove(self, song):
        current = self.head
        while current:
            if current.song.file_path == song.file_path:
                if current.prev:
                    current.prev.next = current.next
                else:
                    self.head = current.next
                
                if current.next:
                    current.next.prev = current.prev
                else:
                    self.tail = current.prev
                
                self.length -= 1
                return True
            current = current.next
        return False
    
    def __iter__(self):
        current = self.head
        while current:
            yield current.song
            current = current.next

class Song:
    def __init__(self, title, artist, album, duration, file_path, playlist="Default"):
        self.title = title
        self.artist = artist
        self.album = album
        self.duration = duration
        self.file_path = file_path
        self.playlist = playlist
        self.play_count = 0
        self.last_played = None
        
    def to_dict(self):
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "file_path": self.file_path,
            "playlist": self.playlist,
            "play_count": self.play_count,
            "last_played": self.last_played
        }

    def get_duration_seconds(self):
        try:
            minutes, seconds = map(int, self.duration.split(':'))
            return minutes * 60 + seconds
        except ValueError:
            return 0

class PlaylistManager:
    def __init__(self):
        self.playlists = {"Default": PlaylistLinkedList()}
        self.current_playlist = "Default"
        self.current_song_index = 0
        self.playing = False
        self.sort_criteria = "title"
        self.sort_order = "ascending"
        self.recently_played = []
        self.favorite_songs = set()  # Using regular set, not frozenset
        self.song_stats = {}
        
    def add_song(self, song, playlist=None):
        if playlist is None:
            playlist = self.current_playlist
        if playlist not in self.playlists:
            self.playlists[playlist] = PlaylistLinkedList()
        self.playlists[playlist].append(song)
        
        if song.file_path not in self.song_stats:
            self.song_stats[song.file_path] = {
                'play_count': 0,
                'last_played': None
            }
    
    def create_playlist(self, name):
        if name not in self.playlists:
            self.playlists[name] = PlaylistLinkedList()
            return True
        return False
    
    def rename_playlist(self, old_name, new_name):
        if old_name in self.playlists and new_name not in self.playlists:
            self.playlists[new_name] = self.playlists.pop(old_name)
            
            # Update songs' playlist attribute
            for song in self.playlists[new_name]:
                song.playlist = new_name
                
            # Update current playlist if needed
            if self.current_playlist == old_name:
                self.current_playlist = new_name
            return True
        return False
    
    def delete_playlist(self, name):
        if name in self.playlists and name != "Default":
            # Move songs to Default playlist
            for song in self.playlists[name]:
                song.playlist = "Default"
                self.playlists["Default"].append(song)
            
            del self.playlists[name]
            
            # Update current playlist if needed
            if self.current_playlist == name:
                self.current_playlist = "Default"
            return True
        return False
    
    def update_song(self, old_song, new_song_data):
        for playlist in self.playlists.values():
            playlist.remove(old_song)
            
        new_playlist = new_song_data.get("playlist", self.current_playlist)
        if new_playlist not in self.playlists:
            self.playlists[new_playlist] = PlaylistLinkedList()
            
        updated_song = Song(
            title=new_song_data["title"],
            artist=new_song_data["artist"],
            album=new_song_data["album"],
            duration=old_song.duration,
            file_path=old_song.file_path,
            playlist=new_playlist
        )
        
        if old_song.file_path in self.song_stats:
            updated_song.play_count = old_song.play_count
            updated_song.last_played = old_song.last_played
            self.song_stats[updated_song.file_path] = {
                'play_count': updated_song.play_count,
                'last_played': updated_song.last_played
            }
            
        self.playlists[new_playlist].append(updated_song)
    
    def delete_song(self, song_to_delete):
        for playlist_name in self.playlists:
            self.playlists[playlist_name].remove(song_to_delete)
        
        if song_to_delete.file_path in self.favorite_songs:
            self.favorite_songs.remove(song_to_delete.file_path)
            
        if song_to_delete.file_path in self.song_stats:
            del self.song_stats[song_to_delete.file_path]
    
    def get_current_playlist_songs(self):
        songs = list(self.playlists.get(self.current_playlist, PlaylistLinkedList()))
        return self.merge_sort(songs, self.sort_criteria, self.sort_order)
    
    def save_to_file(self, filename):
        data = {
            "playlists": {
                name: [song.to_dict() for song in playlist]
                for name, playlist in self.playlists.items()
            },
            "favorites": list(self.favorite_songs),
            "song_stats": self.song_stats,
            "current_playlist": self.current_playlist
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_from_file(self, filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
                for playlist_name, songs_data in data.get("playlists", {}).items():
                    self.playlists[playlist_name] = PlaylistLinkedList()
                    for song_data in songs_data:
                        song = Song(**{k: v for k, v in song_data.items() if k != 'play_count' and k != 'last_played'})
                        
                        if 'play_count' in song_data:
                            song.play_count = song_data['play_count']
                        if 'last_played' in song_data:
                            song.last_played = song_data['last_played']
                            
                        self.playlists[playlist_name].append(song)
                        
                        if song.file_path not in self.song_stats:
                            self.song_stats[song.file_path] = {
                                'play_count': song.play_count,
                                'last_played': song.last_played
                            }
                
                self.favorite_songs = set(data.get("favorites", []))
                self.current_playlist = data.get("current_playlist", "Default")
                
        except (FileNotFoundError, json.JSONDecodeError):
            self.save_to_file(filename)
    
    def merge_sort(self, arr, criteria, order):
        if len(arr) <= 1:
            return arr

        mid = len(arr) // 2
        left_half = arr[:mid]
        right_half = arr[mid:]

        left_half = self.merge_sort(left_half, criteria, order)
        right_half = self.merge_sort(right_half, criteria, order)

        return self._merge(left_half, right_half, criteria, order)

    def _merge(self, left, right, criteria, order):
        merged = []
        left_idx = 0
        right_idx = 0

        while left_idx < len(left) and right_idx < len(right):
            val_left = None
            val_right = None

            if criteria == "duration":
                val_left = left[left_idx].get_duration_seconds()
                val_right = right[right_idx].get_duration_seconds()
            elif criteria == "play_count":
                val_left = left[left_idx].play_count
                val_right = right[right_idx].play_count
            elif criteria == "last_played":
                val_left = left[left_idx].last_played or 0
                val_right = right[right_idx].last_played or 0
            else:
                val_left = getattr(left[left_idx], criteria).lower()
                val_right = getattr(right[right_idx], criteria).lower()

            if order == "ascending":
                if val_left < val_right:
                    merged.append(left[left_idx])
                    left_idx += 1
                else:
                    merged.append(right[right_idx])
                    right_idx += 1
            else:
                if val_left > val_right:
                    merged.append(left[left_idx])
                    left_idx += 1
                else:
                    merged.append(right[right_idx])
                    right_idx += 1

        while left_idx < len(left):
            merged.append(left[left_idx])
            left_idx += 1

        while right_idx < len(right):
            merged.append(right[right_idx])
            right_idx += 1
        
        return merged
    
    def record_play(self, song):
        song.play_count += 1
        song.last_played = time.time()
        
        if song.file_path in self.song_stats:
            self.song_stats[song.file_path]['play_count'] += 1
            self.song_stats[song.file_path]['last_played'] = song.last_played
        else:
            self.song_stats[song.file_path] = {
                'play_count': 1,
                'last_played': song.last_played
            }
        
        if song in self.recently_played:
            self.recently_played.remove(song)
        self.recently_played.insert(0, song)
        if len(self.recently_played) > 10:
            self.recently_played = self.recently_played[:10]
        
    def toggle_favorite(self, song):
        if song.file_path in self.favorite_songs:
            self.favorite_songs.remove(song.file_path)
            return False
        else:
            self.favorite_songs.add(song.file_path)
            return True
    
    def is_favorite(self, song):
        return song.file_path in self.favorite_songs
    
    def get_most_played_songs(self, n=5):
        all_songs = []
        for playlist in self.playlists.values():
            all_songs.extend(list(playlist))
        
        sorted_songs = sorted(all_songs, key=lambda x: x.play_count, reverse=True)
        return sorted_songs[:n]
    
    def get_recently_played(self, n=5):
        return self.recently_played[:n]

class SongMetadataDialog(tk.Toplevel):
    def __init__(self, parent, default_title="", default_artist="", default_album="", playlists=[], current_playlist=""):
        super().__init__(parent)
        self.title("Edit Song Metadata")
        self.geometry("400x300")
        self.resizable(False, False)
        
        self.result = None
        
        tk.Label(self, text="Title:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.title_entry = tk.Entry(self)
        self.title_entry.insert(0, default_title)
        self.title_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        tk.Label(self, text="Artist:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.artist_entry = tk.Entry(self)
        self.artist_entry.insert(0, default_artist)
        self.artist_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        tk.Label(self, text="Album:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.album_entry = tk.Entry(self)
        self.album_entry.insert(0, default_album)
        self.album_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        tk.Label(self, text="Playlist:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.playlist_var = tk.StringVar(value=current_playlist)
        self.playlist_dropdown = ttk.Combobox(self, 
                                            textvariable=self.playlist_var,
                                            values=playlists,
                                            state="readonly")
        self.playlist_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        button_frame = tk.Frame(self)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        tk.Button(button_frame, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        self.grid_columnconfigure(1, weight=1)
        
    def on_ok(self):
        self.result = {
            "title": self.title_entry.get(),
            "artist": self.artist_entry.get(),
            "album": self.album_entry.get(),
            "playlist": self.playlist_var.get()
        }
        self.destroy()

class PlaylistManagerDialog(tk.Toplevel):
    def __init__(self, parent, current_playlists):
        super().__init__(parent)
        self.title("Manage Playlists")
        self.geometry("400x300")
        self.resizable(False, False)
        
        self.result = None
        self.current_playlists = current_playlists
        
        # Create playlist frame
        create_frame = ttk.LabelFrame(self, text="Create New Playlist", padding=10)
        create_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.new_playlist_name = tk.StringVar()
        ttk.Entry(create_frame, textvariable=self.new_playlist_name).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(create_frame, text="Create", command=self.create_playlist).pack(side=tk.LEFT, padx=5)
        
        # Rename playlist frame
        rename_frame = ttk.LabelFrame(self, text="Rename Playlist", padding=10)
        rename_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.rename_old = tk.StringVar()
        self.rename_new = tk.StringVar()
        
        ttk.Combobox(rename_frame, 
                    textvariable=self.rename_old,
                    values=list(current_playlists),
                    state="readonly").pack(fill=tk.X)
        ttk.Entry(rename_frame, textvariable=self.rename_new).pack(fill=tk.X, pady=5)
        ttk.Button(rename_frame, text="Rename", command=self.rename_playlist).pack()
        
        # Delete playlist frame
        delete_frame = ttk.LabelFrame(self, text="Delete Playlist", padding=10)
        delete_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.delete_name = tk.StringVar()
        ttk.Combobox(delete_frame, 
                     textvariable=self.delete_name,
                     values=[p for p in current_playlists if p != "Default"],
                     state="readonly").pack(fill=tk.X)
        ttk.Button(delete_frame, text="Delete", command=self.delete_playlist).pack(pady=5)
        
        # Close button
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=10)
        
    def create_playlist(self):
        name = self.new_playlist_name.get().strip()
        if name and name not in self.current_playlists:
            self.result = ("create", name)
            self.destroy()
        elif not name:
            messagebox.showwarning("Warning", "Please enter a playlist name")
        else:
            messagebox.showwarning("Warning", "Playlist already exists")
    
    def rename_playlist(self):
        old_name = self.rename_old.get()
        new_name = self.rename_new.get().strip()
        
        if not old_name:
            messagebox.showwarning("Warning", "Please select a playlist to rename")
        elif not new_name:
            messagebox.showwarning("Warning", "Please enter a new name")
        elif new_name in self.current_playlists:
            messagebox.showwarning("Warning", "Playlist name already exists")
        else:
            self.result = ("rename", old_name, new_name)
            self.destroy()
    
    def delete_playlist(self):
        name = self.delete_name.get()
        if not name:
            messagebox.showwarning("Warning", "Please select a playlist to delete")
        elif name == "Default":
            messagebox.showwarning("Warning", "Cannot delete Default playlist")
        else:
            self.result = ("delete", name)
            self.destroy()

class MusicPlayerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Player")
        self.root.geometry("900x650")
        
        self.playlist_manager = PlaylistManager()
        self.playlist_manager.load_from_file("music_library.json")
        
        self.setup_ui()
        self.refresh_song_list()
        self.update_playlist_dropdown()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.current_shuffle_index = 0
    
    def setup_ui(self):
        # Main frames
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X)
        
        playlist_frame = ttk.Frame(self.root, padding=10)
        playlist_frame.pack(fill=tk.BOTH, expand=True)
        
        # Playback controls
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(side=tk.LEFT)
        
        ttk.Button(btn_frame, text="Play", command=self.play_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Pause", command=self.pause_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Stop", command=self.stop_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Next", command=self.next_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Prev", command=self.prev_song).pack(side=tk.LEFT, padx=2)
        
        # Volume control
        volume_frame = ttk.Frame(control_frame)
        volume_frame.pack(side=tk.RIGHT)
        ttk.Label(volume_frame, text="Volume:").pack(side=tk.LEFT)
        self.volume_slider = ttk.Scale(volume_frame, from_=0, to=100, command=self.set_volume)
        self.volume_slider.set(70)
        self.volume_slider.pack(side=tk.LEFT)
        
        # Playlist selection
        playlist_select_frame = ttk.Frame(control_frame)
        playlist_select_frame.pack(side=tk.RIGHT, padx=10)
        ttk.Label(playlist_select_frame, text="Playlist:").pack(side=tk.LEFT)
        self.playlist_var = tk.StringVar()
        self.playlist_dropdown = ttk.Combobox(
            playlist_select_frame, 
            textvariable=self.playlist_var,
            values=list(self.playlist_manager.playlists.keys()),
            state="readonly"
        )
        self.playlist_dropdown.set(self.playlist_manager.current_playlist)
        self.playlist_dropdown.pack(side=tk.LEFT)
        self.playlist_dropdown.bind("<<ComboboxSelected>>", self.change_playlist)
        
        # Add Manage Playlists button
        ttk.Button(playlist_select_frame, text="Manage", command=self.manage_playlists).pack(side=tk.LEFT, padx=5)
        
        # Search controls
        search_frame = ttk.Frame(control_frame)
        search_frame.pack(side=tk.RIGHT, padx=10)
        
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=tk.LEFT)
        self.search_entry.bind("<Return>", self.perform_search)
        
        ttk.Button(search_frame, text="Search", command=self.perform_search).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT)
        
        # Sort controls
        sort_frame = ttk.Frame(control_frame)
        sort_frame.pack(side=tk.RIGHT, padx=10)
        
        ttk.Label(sort_frame, text="Sort:").pack(side=tk.LEFT)
        self.sort_criteria = ttk.Combobox(sort_frame, 
                                        values=["Title", "Artist", "Album", "Duration", "Play Count"],
                                        state="readonly",
                                        width=10)
        self.sort_criteria.current(0)
        self.sort_criteria.pack(side=tk.LEFT)
        self.sort_criteria.bind("<<ComboboxSelected>>", self.set_sort_criteria)
        
        self.sort_order = ttk.Combobox(sort_frame, 
                                     values=["Ascending", "Descending"],
                                     state="readonly",
                                     width=10)
        self.sort_order.current(0)
        self.sort_order.pack(side=tk.LEFT)
        self.sort_order.bind("<<ComboboxSelected>>", self.set_sort_order)
        
        # Song list
        self.song_list = ttk.Treeview(playlist_frame, columns=("title", "artist", "album", "duration"), show="headings")
        self.song_list.heading("title", text="Title")
        self.song_list.heading("artist", text="Artist")
        self.song_list.heading("album", text="Album")
        self.song_list.heading("duration", text="Duration")
        
        scrollbar = ttk.Scrollbar(playlist_frame, orient="vertical", command=self.song_list.yview)
        self.song_list.configure(yscrollcommand=scrollbar.set)
        
        self.song_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.song_list.bind("<Double-1>", self.on_song_double_click)
        
        # Now playing info
        self.now_playing_frame = ttk.Frame(self.root, padding=10)
        self.now_playing_frame.pack(fill=tk.X)
        
        self.album_art_img = None
        self.album_art_label = ttk.Label(self.now_playing_frame)
        self.album_art_label.pack(side=tk.LEFT, padx=10)
        
        self.now_playing_info = ttk.Label(self.now_playing_frame, text="No song selected", wraplength=600)
        self.now_playing_info.pack(fill=tk.X, expand=True)
        
        # Progress bar
        self.progress_frame = ttk.Frame(self.root)
        self.progress_frame.pack(fill=tk.X, padx=10)
        self.progress_label = ttk.Label(self.progress_frame, text="00:00 / 00:00")
        self.progress_label.pack(side=tk.RIGHT)
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True)
        
        # Action buttons
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(action_frame, text="Add Songs", command=self.add_songs).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Edit Song", command=self.edit_selected_song).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Delete Song", command=self.delete_selected_song).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Toggle Favorite", command=self.toggle_favorite).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Stats", command=self.show_stats).pack(side=tk.LEFT, padx=5)
        
        self.update_progress()
    
    def manage_playlists(self):
        dialog = PlaylistManagerDialog(self.root, list(self.playlist_manager.playlists.keys()))
        self.root.wait_window(dialog)
        
        if dialog.result:
            action, *args = dialog.result
            if action == "create":
                if self.playlist_manager.create_playlist(args[0]):
                    messagebox.showinfo("Success", f"Playlist '{args[0]}' created")
                    self.update_playlist_dropdown()
                else:
                    messagebox.showwarning("Warning", "Playlist already exists")
            elif action == "rename":
                if self.playlist_manager.rename_playlist(args[0], args[1]):
                    messagebox.showinfo("Success", f"Playlist renamed to '{args[1]}'")
                    self.update_playlist_dropdown()
                else:
                    messagebox.showwarning("Warning", "Failed to rename playlist")
            elif action == "delete":
                if self.playlist_manager.delete_playlist(args[0]):
                    messagebox.showinfo("Success", "Playlist deleted")
                    self.update_playlist_dropdown()
                else:
                    messagebox.showwarning("Warning", "Failed to delete playlist")
            
            self.playlist_manager.save_to_file("music_library.json")
            self.refresh_song_list()
    
    def update_playlist_dropdown(self):
        current = self.playlist_var.get()
        self.playlist_dropdown['values'] = list(self.playlist_manager.playlists.keys())
        
        # Try to maintain current selection if it still exists
        if current in self.playlist_manager.playlists:
            self.playlist_var.set(current)
        else:
            self.playlist_var.set("Default")
            self.playlist_manager.current_playlist = "Default"
    
    def perform_search(self, event=None):
        search_term = self.search_var.get().lower()
        
        if not search_term:
            self.clear_search()
            return
        
        songs = self.playlist_manager.get_current_playlist_songs()
        
        matched_songs = [
            song for song in songs 
            if (search_term in song.title.lower() or 
                search_term in song.artist.lower() or 
                search_term in song.album.lower())
        ]
        
        self.song_list.delete(*self.song_list.get_children())
        for song in matched_songs:
            self.song_list.insert("", tk.END,
                                values=(song.title, song.artist, song.album, song.duration))
        
        if matched_songs:
            first_item = self.song_list.get_children()[0]
            self.song_list.selection_set(first_item)
            self.song_list.see(first_item)
    
    def clear_search(self):
        self.search_var.set("")
        self.refresh_song_list()
    
    def play_song(self):
        selected = self.song_list.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a song to play")
            return
            
        selected_item = selected[0]
        display_index = self.song_list.index(selected_item)
        
        # Get the currently displayed songs (may be filtered by search)
        displayed_songs = []
        for item in self.song_list.get_children():
            values = self.song_list.item(item, 'values')
            # Find the matching song in the current playlist
            for song in self.playlist_manager.get_current_playlist_songs():
                if (song.title == values[0] and 
                    song.artist == values[1] and 
                    song.album == values[2] and 
                    song.duration == values[3]):
                    displayed_songs.append(song)
                    break
        
        # Verify we have a valid index
        if 0 <= display_index < len(displayed_songs):
            song_to_play = displayed_songs[display_index]
            all_songs = self.playlist_manager.get_current_playlist_songs()
            
            try:
                # Find the actual index in the complete playlist
                actual_index = all_songs.index(song_to_play)
                self.playlist_manager.current_song_index = actual_index
                self.play_song_at_index(actual_index)
                
                # Highlight the playing song in the list
                children = self.song_list.get_children()
                if children and display_index < len(children):
                    self.song_list.selection_set(children[display_index])
                    self.song_list.see(children[display_index])
            except ValueError:
                messagebox.showerror("Error", "Song not found in playlist")
        else:
            messagebox.showwarning("Error", "Invalid song index")

    def play_song_at_index(self, index):
        songs = self.playlist_manager.get_current_playlist_songs()
        if not songs or index >= len(songs):
            return

        song = songs[index]
        try:
            pygame.mixer.music.load(song.file_path)
            pygame.mixer.music.play()
            self.playlist_manager.playing = True
            self.playlist_manager.record_play(song)
            self.update_now_playing(song)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot play song: {str(e)}")

    def update_now_playing(self, song):
        favorite_status = "⭐" if self.playlist_manager.is_favorite(song) else ""
        self.now_playing_info.config(
            text=f"Now Playing: {song.title} {favorite_status}\nArtist: {song.artist}\nAlbum: {song.album} | Duration: {song.duration}"
        )
        
        try:
            audiofile = eyed3.load(song.file_path)
            if audiofile and audiofile.tag and audiofile.tag.images:
                image_data = audiofile.tag.images[0].image_data
                img = Image.open(io.BytesIO(image_data))
                img.thumbnail((100, 100))
                self.album_art_img = ImageTk.PhotoImage(img)
                self.album_art_label.config(image=self.album_art_img)
            else:
                self.album_art_label.config(image='')
        except Exception:
            self.album_art_label.config(image='')
    
    def pause_song(self):
        if pygame.mixer.music.get_busy():
            if self.playlist_manager.playing:
                pygame.mixer.music.pause()
                self.playlist_manager.playing = False
            else:
                pygame.mixer.music.unpause()
                self.playlist_manager.playing = True
    
    def stop_song(self):
        pygame.mixer.music.stop()
        self.playlist_manager.playing = False
        self.now_playing_info.config(text="Playback stopped")
        self.progress_bar['value'] = 0
        self.progress_label.config(text="00:00 / 00:00")
        
    def next_song(self):
        songs = self.playlist_manager.get_current_playlist_songs()
        if not songs:
            return
            
        next_index = (self.playlist_manager.current_song_index + 1) % len(songs)
        if next_index == 0:
            self.stop_song()
            return
            
        self.playlist_manager.current_song_index = next_index
        self.play_song_at_index(next_index)
        
    def prev_song(self):
        songs = self.playlist_manager.get_current_playlist_songs()
        if not songs:
            return
            
        prev_index = (self.playlist_manager.current_song_index - 1) % len(songs)
        if prev_index == len(songs) - 1:
            self.stop_song()
            return
            
        self.playlist_manager.current_song_index = prev_index
        self.play_song_at_index(prev_index)
        
    def set_volume(self, val):
        volume = float(val) / 100
        pygame.mixer.music.set_volume(volume)
        
    def update_progress(self):
        if pygame.mixer.music.get_busy() and self.playlist_manager.playing:
            current_pos = pygame.mixer.music.get_pos() / 1000
            songs = self.playlist_manager.get_current_playlist_songs()
            if songs and self.playlist_manager.current_song_index < len(songs):
                song = songs[self.playlist_manager.current_song_index]
                try:
                    duration_seconds = song.get_duration_seconds()
                    
                    if duration_seconds > 0:
                        progress = (current_pos / duration_seconds) * 100
                        self.progress_bar['value'] = progress
                        
                        current_time = f"{int(current_pos // 60):02d}:{int(current_pos % 60):02d}"
                        total_time = song.duration
                        self.progress_label.config(text=f"{current_time} / {total_time}")
                except:
                    pass
                
        self.root.after(1000, self.update_progress)
        
    def on_song_double_click(self, event):
        self.play_song()
        
    def on_closing(self):
        self.playlist_manager.save_to_file("music_library.json")
        pygame.mixer.quit()
        self.root.destroy()
    
    def show_stats(self):
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Music Statistics")
        
        notebook = ttk.Notebook(stats_window)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Most played tab
        most_played_frame = ttk.Frame(notebook)
        notebook.add(most_played_frame, text="Most Played")
        
        most_played = self.playlist_manager.get_most_played_songs(10)
        tree = ttk.Treeview(most_played_frame, columns=("title", "artist", "plays"), show="headings")
        tree.heading("title", text="Title")
        tree.heading("artist", text="Artist")
        tree.heading("plays", text="Play Count")
        
        for song in most_played:
            tree.insert("", tk.END, values=(song.title, song.artist, song.play_count))
        
        tree.pack(fill=tk.BOTH, expand=True)
        
        # Recently played tab
        recent_frame = ttk.Frame(notebook)
        notebook.add(recent_frame, text="Recently Played")
        
        recent = self.playlist_manager.get_recently_played(10)
        tree = ttk.Treeview(recent_frame, columns=("title", "artist", "last_played"), show="headings")
        tree.heading("title", text="Title")
        tree.heading("artist", text="Artist")
        tree.heading("last_played", text="Last Played")
        
        for song in recent:
            last_played = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(song.last_played)) if song.last_played else "Never"
            tree.insert("", tk.END, values=(song.title, song.artist, last_played))
        
        tree.pack(fill=tk.BOTH, expand=True)
    
    def toggle_favorite(self):
        selected_item = self.song_list.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a song first.")
            return
            
        index = self.song_list.index(selected_item[0])
        songs = self.playlist_manager.get_current_playlist_songs()
        
        if index < len(songs):
            song = songs[index]
            is_favorite = self.playlist_manager.toggle_favorite(song)
            self.playlist_manager.save_to_file("music_library.json")
            
            if is_favorite:
                messagebox.showinfo("Info", f"Song '{song.title}' added to favorites.")
            else:
                messagebox.showinfo("Info", f"Song '{song.title}' removed from favorites.")
    
    def set_sort_criteria(self, event=None):
        selected_criteria = self.sort_criteria.get().lower().replace(" ", "_")
        self.playlist_manager.sort_criteria = selected_criteria
        self.refresh_song_list()

    def set_sort_order(self, event=None):
        selected_order = self.sort_order.get().lower()
        self.playlist_manager.sort_order = selected_order
        self.refresh_song_list()

    def refresh_song_list(self):
        self.song_list.delete(*self.song_list.get_children())
        songs = self.playlist_manager.get_current_playlist_songs()
        for song in songs:
            self.song_list.insert("", tk.END, values=(song.title, song.artist, song.album, song.duration))
        
    def change_playlist(self, event=None):
        selected_playlist = self.playlist_var.get()
        self.playlist_manager.current_playlist = selected_playlist
        self.playlist_manager.current_song_index = 0
        self.refresh_song_list()
        
    def add_songs(self):
        file_paths = filedialog.askopenfilenames(
            title="Select MP3 Files",
            filetypes=[("MP3 Files", "*.mp3"), ("All Files", "*.*")]
        )
        
        if not file_paths:
            return
            
        for file_path in file_paths:
            try:
                audiofile = eyed3.load(file_path)
                title = os.path.splitext(os.path.basename(file_path))[0]
                artist = "Unknown Artist"
                album = "Unknown Album"
                duration = "0:00"

                if audiofile and audiofile.tag:
                    tag = audiofile.tag
                    title = tag.title or title
                    artist = tag.artist or artist
                    album = tag.album or album
                
                if audiofile and audiofile.info and audiofile.info.time_secs is not None:
                    try:
                        duration_seconds = int(audiofile.info.time_secs)
                        minutes, seconds = divmod(duration_seconds, 60)
                        duration = f"{minutes}:{seconds:02d}"
                    except (AttributeError, TypeError):
                        duration = "0:00"
                
                # Show dialog to edit metadata before adding
                dialog = SongMetadataDialog(
                    self.root,
                    default_title=title,
                    default_artist=artist,
                    default_album=album,
                    playlists=list(self.playlist_manager.playlists.keys()),
                    current_playlist=self.playlist_manager.current_playlist
                )
                self.root.wait_window(dialog)
                
                if dialog.result:
                    song = Song(
                        title=dialog.result["title"],
                        artist=dialog.result["artist"],
                        album=dialog.result["album"],
                        duration=duration,
                        file_path=file_path,
                        playlist=dialog.result["playlist"]
                    )
                    
                    self.playlist_manager.add_song(song, dialog.result["playlist"])
            
            except Exception as e:
                messagebox.showerror("Error", f"Cannot load {file_path}: {str(e)}")
                continue
                
        self.playlist_manager.save_to_file("music_library.json")
        self.refresh_song_list()
        messagebox.showinfo("Success", f"Added {len(file_paths)} songs")

    def edit_selected_song(self):
        selected_item = self.song_list.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a song to edit.")
            return

        index = self.song_list.index(selected_item[0])
        songs = self.playlist_manager.get_current_playlist_songs()
        
        if index < len(songs):
            song = songs[index]
            
            dialog = SongMetadataDialog(
                self.root,
                default_title=song.title,
                default_artist=song.artist,
                default_album=song.album,
                playlists=list(self.playlist_manager.playlists.keys()),
                current_playlist=song.playlist
            )
            self.root.wait_window(dialog)
            
            if dialog.result:
                self.playlist_manager.update_song(song, dialog.result)
                self.playlist_manager.save_to_file("music_library.json")
                self.refresh_song_list()
                messagebox.showinfo("Success", "Song updated")

    def delete_selected_song(self):
        selected_item = self.song_list.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a song to delete.")
            return

        index = self.song_list.index(selected_item[0])
        songs = self.playlist_manager.get_current_playlist_songs()
        
        if index < len(songs):
            song = songs[index]
            
            confirm = messagebox.askyesno(
                "Confirm Deletion",
                f"Delete '{song.title}' from all playlists?"
            )
            if confirm:
                self.playlist_manager.delete_song(song)
                self.playlist_manager.save_to_file("music_library.json")
                self.refresh_song_list()
                messagebox.showinfo("Success", "Song deleted")

if __name__ == "__main__":
    root = tk.Tk()
    app = MusicPlayerApp(root)
    root.mainloop()