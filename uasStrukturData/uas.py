# Impor semua library yang diperlukan
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import pygame
import eyed3
from PIL import Image, ImageTk
import io
import time

# Inisialisasi pygame mixer untuk pemutaran audio
pygame.mixer.init()

# ==================================================
# KELAS STRUKTUR DATA (Tidak ada perubahan signifikan)
# ==================================================
class SongNode:
    """Node untuk linked list ganda yang menyimpan data lagu"""
    def __init__(self, song, next_node=None, prev_node=None):
        self.song = song      # Menyimpan objek lagu
        self.next = next_node  # Pointer ke node berikutnya
        self.prev = prev_node  # Pointer ke node sebelumnya


class PlaylistLinkedList:
    """Implementasi linked list ganda untuk playlist lagu"""
    def __init__(self):
        self.head = None     # Node pertama
        self.tail = None     # Node terakhir
        self.length = 0      # Jumlah lagu

    def append(self, song):
        """Menambahkan lagu ke akhir playlist"""
        new_node = SongNode(song)
        if not self.head:  # Jika playlist kosong
            self.head = new_node
            self.tail = new_node
        else:  # Jika playlist tidak kosong
            new_node.prev = self.tail
            self.tail.next = new_node
            self.tail = new_node
        self.length += 1

    def remove(self, song):
        """Menghapus lagu dari playlist"""
        current = self.head
        while current:  # Cari lagu yang akan dihapus
            if current.song.file_path == song.file_path:
                # Perbarui pointer node sebelum dan sesudah
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
        """Membuat playlist bisa diiterasi"""
        current = self.head
        while current:
            yield current.song
            current = current.next
    
    def __len__(self):
        """Mengembalikan jumlah lagu dalam playlist"""
        return self.length


class Song:
    """Kelas untuk merepresentasikan sebuah lagu beserta metadatanya"""
    def __init__(self, title, artist, album, duration, file_path, playlist="Default"):
        self.title = title       # Judul lagu
        self.artist = artist     # Nama artis
        self.album = album       # Nama album
        self.duration = duration # Durasi lagu (format MM:SS)
        self.file_path = file_path # Lokasi file lagu
        self.playlist = playlist # Nama playlist
        self.play_count = 0      # Jumlah kali diputar
        self.last_played = None  # Waktu terakhir diputar

    def to_dict(self):
        """Mengubah objek lagu menjadi dictionary untuk penyimpanan"""
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
        """Mengubah durasi lagu menjadi detik"""
        try:
            minutes, seconds = map(int, self.duration.split(':'))
            return minutes * 60 + seconds
        except ValueError:
            return 0


# ==================================================
# KELAS MANAJEMEN PLAYLIST
# ==================================================
class PlaylistManager:
    """Kelas untuk mengelola semua playlist dan operasinya"""
    def __init__(self):
        self.playlists = {"Default": PlaylistLinkedList()}  # Daftar playlist
        self.current_playlist = "Default"  # Playlist aktif
        self.current_song_index = 0      # Indeks lagu yang sedang diputar
        self.playing = False             # Status pemutaran
        self.sort_criteria = "title"     # Kriteria pengurutan
        self.sort_order = "ascending"  # Urutan pengurutan
        self.recently_played = []        # Riwayat lagu yang diputar
        self.favorite_songs = set()      # Daftar lagu favorit
        self.song_stats = {}             # Statistik lagu

    def add_song(self, song, playlist=None):
        if playlist is None:
            playlist = self.current_playlist
        if playlist not in self.playlists:
            self.playlists[playlist] = PlaylistLinkedList()
        self.playlists[playlist].append(song)
        if song.file_path not in self.song_stats:
            self.song_stats[song.file_path] = {
                'play_count': 0, 'last_played': None
            }

    def create_playlist(self, name):
        if name not in self.playlists:
            self.playlists[name] = PlaylistLinkedList()
            return True
        return False

    def rename_playlist(self, old_name, new_name):
        if old_name in self.playlists and new_name not in self.playlists:
            self.playlists[new_name] = self.playlists.pop(old_name)
            for song in self.playlists[new_name]:
                song.playlist = new_name
            if self.current_playlist == old_name:
                self.current_playlist = new_name
            return True
        return False

    def delete_playlist(self, name):
        if name in self.playlists and name != "Default":
            for song in self.playlists[name]:
                song.playlist = "Default"
                self.playlists["Default"].append(song)
            del self.playlists[name]
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
            title=new_song_data["title"], artist=new_song_data["artist"],
            album=new_song_data["album"], duration=old_song.duration,
            file_path=old_song.file_path, playlist=new_playlist
        )
        if old_song.file_path in self.song_stats:
            updated_song.play_count = old_song.play_count
            updated_song.last_played = old_song.last_played
            self.song_stats[updated_song.file_path] = {
                'play_count': updated_song.play_count, 'last_played': updated_song.last_played
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
        # Untuk mendapatkan lagu tanpa diurutkan, panggil langsung
        return songs
    
    def get_sorted_playlist_songs(self):
        """Mendapatkan daftar lagu di playlist aktif dan mengurutkannya."""
        songs = list(self.playlists.get(self.current_playlist, PlaylistLinkedList()))
        # Panggil merge_sort biasa (non-generator) untuk hasil akhir
        return self._merge_sort_final(songs, self.sort_criteria, self.sort_order)


    def get_total_song_count(self):
        unique_songs = set()
        for playlist in self.playlists.values():
            for song in playlist:
                unique_songs.add(song.file_path)
        return len(unique_songs)

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
            json.dump(data, f, indent=4)

    def load_from_file(self, filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                for playlist_name, songs_data in data.get("playlists", {}).items():
                    self.playlists[playlist_name] = PlaylistLinkedList()
                    for song_data in songs_data:
                        song = Song(
                            title=song_data.get('title', 'Unknown Title'),
                            artist=song_data.get('artist', 'Unknown Artist'),
                            album=song_data.get('album', 'Unknown Album'),
                            duration=song_data.get('duration', '0:00'),
                            file_path=song_data.get('file_path'),
                            playlist=song_data.get('playlist', 'Default')
                        )
                        song.play_count = song_data.get('play_count', 0)
                        song.last_played = song_data.get('last_played', None)
                        if song.file_path:
                            self.playlists[playlist_name].append(song)
                            if song.file_path not in self.song_stats:
                                self.song_stats[song.file_path] = {
                                    'play_count': song.play_count,
                                    'last_played': song.last_played
                                }
                self.favorite_songs = set(data.get("favorites", []))
                self.current_playlist = data.get("current_playlist", "Default")
                if self.current_playlist not in self.playlists:
                    self.current_playlist = "Default"
        except (FileNotFoundError, json.JSONDecodeError):
            self.save_to_file(filename)

    # --- PERUBAHAN UNTUK ANIMASI SORTING ---
    def merge_sort_for_animation(self, arr, criteria, order, start_index=0):
        """Generator merge sort untuk animasi, menghasilkan langkah-langkah."""
        if len(arr) <= 1:
            return arr

        mid = len(arr) // 2
        left_half = arr[:mid]
        right_half = arr[mid:]

        # Rekursif panggil generator pada sub-array
        yield from self.merge_sort_for_animation(left_half, criteria, order, start_index)
        yield from self.merge_sort_for_animation(right_half, criteria, order, start_index + mid)

        # Gabungkan dan yield langkah-langkahnya
        yield from self._merge_for_animation(left_half, right_half, criteria, order, start_index)
    
    def _get_song_value(self, song, criteria):
        """Helper untuk mendapatkan nilai dari lagu berdasarkan kriteria."""
        if criteria == "duration":
            return song.get_duration_seconds()
        if criteria == "play_count":
            return song.play_count
        if criteria == "last_played":
            return song.last_played or 0
        # Untuk title, artist, album
        return getattr(song, criteria, "").lower()

    def _merge_for_animation(self, left, right, criteria, order, start_index):
        """Generator untuk proses merge, menghasilkan status perbandingan."""
        merged = []
        left_idx, right_idx = 0, 0

        while left_idx < len(left) and right_idx < len(right):
            # Dapatkan nilai untuk perbandingan
            val_left = self._get_song_value(left[left_idx], criteria)
            val_right = self._get_song_value(right[right_idx], criteria)
            
            # Tentukan posisi global dari elemen yang dibandingkan
            global_left_idx = start_index + merged.index(left[left_idx]) if left[left_idx] in merged else start_index + len(merged) + left_idx
            global_right_idx = start_index + merged.index(right[right_idx]) if right[right_idx] in merged else start_index + len(merged) + left_idx + right_idx
            
            # Hasil ('yield') status perbandingan
            yield ('compare', global_left_idx, global_right_idx)

            condition = (val_left < val_right) if order == "ascending" else (val_left > val_right)

            if condition:
                merged.append(left[left_idx])
                left_idx += 1
            else:
                merged.append(right[right_idx])
                right_idx += 1

        merged.extend(left[left_idx:])
        merged.extend(right[right_idx:])
        
        # Hasil ('yield') sub-array yang sudah tergabung untuk pembaruan Treeview
        yield ('merge', start_index, merged)

    def _merge_sort_final(self, arr, criteria, order):
        """Versi merge sort standar (non-generator) untuk mendapatkan hasil akhir."""
        if len(arr) <= 1:
            return arr
        mid = len(arr) // 2
        left_half = self._merge_sort_final(arr[:mid], criteria, order)
        right_half = self._merge_sort_final(arr[mid:], criteria, order)
        return self._merge_final(left_half, right_half, criteria, order)

    def _merge_final(self, left, right, criteria, order):
        """Fungsi helper merge standar."""
        merged = []
        left_idx, right_idx = 0, 0
        while left_idx < len(left) and right_idx < len(right):
            val_left = self._get_song_value(left[left_idx], criteria)
            val_right = self._get_song_value(right[right_idx], criteria)
            condition = (val_left < val_right) if order == "ascending" else (val_left > val_right)
            if condition:
                merged.append(left[left_idx])
                left_idx += 1
            else:
                merged.append(right[right_idx])
                right_idx += 1
        merged.extend(left[left_idx:])
        merged.extend(right[right_idx:])
        return merged

    # ... (Sisa fungsi PlaylistManager tidak berubah) ...
    def record_play(self, song):
        song.play_count += 1
        song.last_played = time.time()
        if song.file_path in self.song_stats:
            self.song_stats[song.file_path]['play_count'] += 1
            self.song_stats[song.file_path]['last_played'] = song.last_played
        else:
            self.song_stats[song.file_path] = {'play_count': 1, 'last_played': song.last_played}
        self.recently_played = [s for s in self.recently_played if s.file_path != song.file_path]
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

    def get_most_played_songs(self, n=10):
        all_songs = []
        unique_paths = set()
        for playlist in self.playlists.values():
            for song in playlist:
                if song.file_path not in unique_paths:
                    all_songs.append(song)
                    unique_paths.add(song.file_path)
        sorted_songs = sorted(all_songs, key=lambda x: x.play_count, reverse=True)
        return sorted_songs[:n]

    def get_recently_played(self, n=10):
        return self.recently_played[:n]


# ==================================================
# KELAS DIALOG GUI (Tidak ada perubahan)
# ==================================================

class SongMetadataDialog(tk.Toplevel):
    """Dialog untuk mengedit metadata lagu"""
    def __init__(self, parent, default_title="", default_artist="", default_album="", playlists=[], current_playlist=""):
        super().__init__(parent)
        self.title("Edit Metadata Lagu")
        self.geometry("400x250")
        self.resizable(False, False)
        self.transient(parent) # Tetap di atas parent
        self.grab_set()
        
        self.result = None  # Untuk menyimpan hasil
        
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Judul:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.insert(0, default_title)
        self.title_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(main_frame, text="Artis:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.artist_entry = ttk.Entry(main_frame)
        self.artist_entry.insert(0, default_artist)
        self.artist_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(main_frame, text="Album:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.album_entry = ttk.Entry(main_frame)
        self.album_entry.insert(0, default_album)
        self.album_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(main_frame, text="Playlist:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.playlist_var = tk.StringVar(value=current_playlist)
        self.playlist_dropdown = ttk.Combobox(main_frame, textvariable=self.playlist_var, values=playlists, state="readonly")
        self.playlist_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=15)
        
        ttk.Button(button_frame, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Batal", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        main_frame.grid_columnconfigure(1, weight=1)

    def on_ok(self):
        self.result = {
            "title": self.title_entry.get() or "Unknown Title",
            "artist": self.artist_entry.get() or "Unknown Artist",
            "album": self.album_entry.get() or "Unknown Album",
            "playlist": self.playlist_var.get()
        }
        self.destroy()

class PlaylistManagerDialog(tk.Toplevel):
    """Dialog untuk mengelola playlist"""
    def __init__(self, parent, current_playlists):
        super().__init__(parent)
        self.title("Kelola Playlist")
        self.geometry("400x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.current_playlists = current_playlists
        
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        create_frame = ttk.LabelFrame(main_frame, text="Buat Playlist Baru", padding=10)
        create_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.new_playlist_name = tk.StringVar()
        ttk.Entry(create_frame, textvariable=self.new_playlist_name).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(create_frame, text="Buat", command=self.create_playlist).pack(side=tk.LEFT)
        
        rename_frame = ttk.LabelFrame(main_frame, text="Ganti Nama Playlist", padding=10)
        rename_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.rename_old = tk.StringVar()
        self.rename_new = tk.StringVar()
        
        ttk.Label(rename_frame, text="Playlist Lama:").pack(anchor='w')
        ttk.Combobox(rename_frame, textvariable=self.rename_old, values=list(current_playlists), state="readonly").pack(fill=tk.X, pady=(0,5))
        ttk.Label(rename_frame, text="Nama Baru:").pack(anchor='w')
        ttk.Entry(rename_frame, textvariable=self.rename_new).pack(fill=tk.X)
        ttk.Button(rename_frame, text="Ganti Nama", command=self.rename_playlist).pack(pady=(10,0))
        
        delete_frame = ttk.LabelFrame(main_frame, text="Hapus Playlist", padding=10)
        delete_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.delete_name = tk.StringVar()
        ttk.Combobox(delete_frame, textvariable=self.delete_name, values=[p for p in current_playlists if p != "Default"], state="readonly").pack(fill=tk.X)
        ttk.Button(delete_frame, text="Hapus", command=self.delete_playlist).pack(pady=(10,0))
        
        ttk.Button(main_frame, text="Tutup", command=self.destroy).pack(pady=10, side=tk.BOTTOM)

    def create_playlist(self):
        name = self.new_playlist_name.get().strip()
        if name and name not in self.current_playlists:
            self.result = ("create", name)
            self.destroy()
        elif not name:
            messagebox.showwarning("Peringatan", "Harap masukkan nama playlist", parent=self)
        else:
            messagebox.showwarning("Peringatan", "Playlist sudah ada", parent=self)

    def rename_playlist(self):
        old_name = self.rename_old.get()
        new_name = self.rename_new.get().strip()
        
        if not old_name:
            messagebox.showwarning("Peringatan", "Harap pilih playlist yang akan diganti namanya", parent=self)
        elif not new_name:
            messagebox.showwarning("Peringatan", "Harap masukkan nama baru", parent=self)
        elif new_name in self.current_playlists:
            messagebox.showwarning("Peringatan", "Nama playlist sudah digunakan", parent=self)
        else:
            self.result = ("rename", old_name, new_name)
            self.destroy()

    def delete_playlist(self):
        name = self.delete_name.get()
        if not name:
            messagebox.showwarning("Peringatan", "Harap pilih playlist yang akan dihapus", parent=self)
        elif name == "Default":
            messagebox.showwarning("Peringatan", "Tidak bisa menghapus playlist Default", parent=self)
        else:
            confirm = messagebox.askyesno("Konfirmasi", f"Yakin ingin menghapus playlist '{name}'? Lagu di dalamnya akan dipindahkan ke 'Default'.", parent=self)
            if confirm:
                self.result = ("delete", name)
                self.destroy()

# ==================================================
# KELAS APLIKASI UTAMA
# ==================================================

class MusicPlayerApp:
    """Kelas utama aplikasi pemutar musik"""
    def __init__(self, root):
        self.root = root
        self.root.title("Pemutar Musik dengan Animasi Sorting")
        self.root.geometry("950x700")
        
        self.playlist_manager = PlaylistManager()
        self.playlist_manager.load_from_file("music_library.json")
        
        self.sort_criteria_map = {
            "Judul": "title", "Artis": "artist", "Album": "album",
            "Durasi": "duration", "Jumlah Diputar": "play_count", "Terakhir Diputar": "last_played"
        }
        self.sort_order_map = {"Naik": "ascending", "Turun": "descending"}
        
        self.is_sorting = False # Flag untuk menandakan animasi sedang berjalan

        self.setup_ui()
        self.update_playlist_dropdown()
        self.refresh_song_list(animate=False) # Muat awal tanpa animasi
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """Mengatur antarmuka pengguna"""
        # --- Frame Atas (Kontrol Utama) ---
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        playback_frame = ttk.LabelFrame(top_frame, text="Kontrol", padding=5)
        playback_frame.pack(side=tk.LEFT, padx=(0, 10), fill=tk.Y)
        self.prev_button = ttk.Button(playback_frame, text="◀◀ Prev", command=self.prev_song)
        self.prev_button.pack(side=tk.LEFT, padx=2)
        self.play_button = ttk.Button(playback_frame, text="▶ Play", command=self.play_song)
        self.play_button.pack(side=tk.LEFT, padx=2)
        self.pause_button = ttk.Button(playback_frame, text="❚❚ Pause", command=self.pause_song)
        self.pause_button.pack(side=tk.LEFT, padx=2)
        self.stop_button = ttk.Button(playback_frame, text="■ Stop", command=self.stop_song)
        self.stop_button.pack(side=tk.LEFT, padx=2)
        self.next_button = ttk.Button(playback_frame, text="▶▶ Next", command=self.next_song)
        self.next_button.pack(side=tk.LEFT, padx=2)
        
        manage_frame = ttk.LabelFrame(top_frame, text="Manajemen", padding=5)
        manage_frame.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(manage_frame, text="Playlist:").pack(side=tk.LEFT, padx=(5,2))
        self.playlist_var = tk.StringVar()
        self.playlist_dropdown = ttk.Combobox(manage_frame, textvariable=self.playlist_var, state="readonly", width=15)
        self.playlist_dropdown.pack(side=tk.LEFT)
        self.playlist_dropdown.bind("<<ComboboxSelected>>", self.change_playlist)
        self.manage_playlist_button = ttk.Button(manage_frame, text="Kelola", command=self.manage_playlists)
        self.manage_playlist_button.pack(side=tk.LEFT, padx=(5,10))
        
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(manage_frame, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=tk.LEFT)
        self.search_entry.bind("<KeyRelease>", self.perform_search)
        ttk.Button(manage_frame, text="✖", command=self.clear_search, width=2).pack(side=tk.LEFT, padx=2)
        
        volume_frame = ttk.Frame(top_frame)
        volume_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Label(volume_frame, text="Volume:").pack()
        self.volume_slider = ttk.Scale(volume_frame, from_=0, to=100, command=self.set_volume, orient=tk.HORIZONTAL)
        self.volume_slider.set(70)
        pygame.mixer.music.set_volume(0.7)
        self.volume_slider.pack()

        # --- Frame Daftar Lagu ---
        list_frame = ttk.Frame(self.root, padding=(10,0,10,0))
        list_frame.pack(fill=tk.BOTH, expand=True)

        sort_frame = ttk.Frame(list_frame)
        sort_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(sort_frame, text="Urutkan berdasarkan:").pack(side=tk.LEFT)
        self.sort_criteria_var = tk.StringVar(value="Judul")
        self.sort_criteria_combo = ttk.Combobox(sort_frame, textvariable=self.sort_criteria_var, values=list(self.sort_criteria_map.keys()), state="readonly", width=15)
        self.sort_criteria_combo.pack(side=tk.LEFT, padx=5)
        self.sort_criteria_combo.bind("<<ComboboxSelected>>", self.set_sort_options)
        
        self.sort_order_var = tk.StringVar(value="Naik")
        self.sort_order_combo = ttk.Combobox(sort_frame, textvariable=self.sort_order_var, values=list(self.sort_order_map.keys()), state="readonly", width=8)
        self.sort_order_combo.pack(side=tk.LEFT)
        self.sort_order_combo.bind("<<ComboboxSelected>>", self.set_sort_options)

        self.song_list = ttk.Treeview(list_frame, columns=("judul", "artis", "album", "durasi"), show="headings")
        self.song_list.heading("judul", text="Judul")
        self.song_list.heading("artis", text="Artis")
        self.song_list.heading("album", text="Album")
        self.song_list.heading("durasi", text="Durasi")
        self.song_list.column("judul", width=300)
        self.song_list.column("artis", width=200)
        self.song_list.column("album", width=200)
        self.song_list.column("durasi", width=80, anchor=tk.E)
        
        # --- PERSIAPAN UNTUK ANIMASI: Buat tag warna ---
        self.song_list.tag_configure('compare', background='#a7c7e7') # Biru muda
        self.song_list.tag_configure('sorted', background='#b2e8b2') # Hijau muda

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.song_list.yview)
        self.song_list.configure(yscrollcommand=scrollbar.set)
        
        self.song_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.song_list.bind("<Double-1>", self.on_song_double_click)
        
        # --- Frame Bawah ---
        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill=tk.X)

        self.album_art_img = None
        self.album_art_label = ttk.Label(bottom_frame, text="Album Art")
        self.album_art_label.pack(side=tk.LEFT, padx=(0, 10))
        self.update_album_art(None)
        
        info_progress_frame = ttk.Frame(bottom_frame)
        info_progress_frame.pack(fill=tk.X, expand=True)

        self.now_playing_info = ttk.Label(info_progress_frame, text="Tidak ada lagu yang diputar", wraplength=600, font=("Segoe UI", 10))
        self.now_playing_info.pack(fill=tk.X, anchor='w')
        
        self.progress_bar = ttk.Progressbar(info_progress_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True, pady=5)
        self.progress_label = ttk.Label(info_progress_frame, text="00:00 / 00:00")
        self.progress_label.pack(fill=tk.X, anchor='e')
        
        action_frame = ttk.Frame(info_progress_frame)
        action_frame.pack(fill=tk.X, pady=(5,0))
        self.add_song_button = ttk.Button(action_frame, text="➕ Tambah Lagu", command=self.add_songs)
        self.add_song_button.pack(side=tk.LEFT, padx=2)
        self.edit_song_button = ttk.Button(action_frame, text="✏️ Edit Lagu", command=self.edit_selected_song)
        self.edit_song_button.pack(side=tk.LEFT, padx=2)
        self.delete_song_button = ttk.Button(action_frame, text="❌ Hapus Lagu", command=self.delete_selected_song)
        self.delete_song_button.pack(side=tk.LEFT, padx=2)
        self.fav_button = ttk.Button(action_frame, text="⭐ Favorit", command=self.toggle_favorite)
        self.fav_button.pack(side=tk.LEFT, padx=2)
        self.stats_button = ttk.Button(action_frame, text="📊 Statistik", command=self.show_stats)
        self.stats_button.pack(side=tk.LEFT, padx=2)
        
        self.status_bar = ttk.Label(self.root, text="Memuat...", anchor=tk.W, relief=tk.SUNKEN, padding=2)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.update_progress()
        
    def toggle_ui_state(self, state=tk.NORMAL):
        """Enable/disable kontrol UI selama animasi."""
        for widget in [self.prev_button, self.play_button, self.pause_button, 
                       self.stop_button, self.next_button, self.manage_playlist_button,
                       self.search_entry, self.sort_criteria_combo, self.sort_order_combo,
                       self.add_song_button, self.edit_song_button, self.delete_song_button,
                       self.fav_button, self.stats_button, self.playlist_dropdown, self.song_list]:
            try:
                widget.config(state=state)
            except tk.TclError: # Treeview tidak punya config state
                 if state == tk.DISABLED:
                     # Mencegah klik pada treeview selama animasi
                     widget.bind("<Button-1>", lambda e: "break")
                 else:
                     widget.unbind("<Button-1>")

    def set_sort_options(self, event=None):
        """Memulai animasi pengurutan saat opsi diubah."""
        if self.is_sorting: return
        
        selected_criteria_display = self.sort_criteria_var.get()
        selected_order_display = self.sort_order_var.get()
        self.playlist_manager.sort_criteria = self.sort_criteria_map[selected_criteria_display]
        self.playlist_manager.sort_order = self.sort_order_map[selected_order_display]
        
        self.start_sort_animation()
        
    def start_sort_animation(self):
        """Mempersiapkan dan memulai generator animasi."""
        self.is_sorting = True
        self.toggle_ui_state(tk.DISABLED) # Nonaktifkan UI
        self.status_bar.config(text=f"Mengurutkan berdasarkan '{self.sort_criteria_var.get()}'...")
        
        # Dapatkan daftar lagu yang saat ini ditampilkan
        songs_in_view = []
        for item_id in self.song_list.get_children():
            # Cari objek Song yang sesuai dengan item di Treeview
            values = self.song_list.item(item_id, 'values')
            # Ini asumsi sederhana. Untuk kasus kompleks, diperlukan mapping yang lebih baik.
            # Kita akan gunakan file_path sebagai ID unik.
            # Dapatkan semua lagu dulu
            all_songs = self.playlist_manager.get_current_playlist_songs()
            found_song = next((s for s in all_songs if s.title == values[0] and s.artist == values[1] and s.album == values[2]), None)
            if found_song:
                songs_in_view.append(found_song)

        if not songs_in_view:
             self.refresh_song_list(animate=False)
             return

        # Buat generator
        self.sort_generator = self.playlist_manager.merge_sort_for_animation(
            songs_in_view, 
            self.playlist_manager.sort_criteria, 
            self.playlist_manager.sort_order
        )
        
        self.animate_sort_step()

    def animate_sort_step(self):
        """Menjalankan satu langkah animasi."""
        try:
            step = next(self.sort_generator)
            action, *args = step
            
            # Hapus semua highlight sebelumnya
            for item_id in self.song_list.get_children():
                self.song_list.item(item_id, tags=())

            if action == 'compare':
                # Tandai item yang sedang dibandingkan
                idx1, idx2 = args
                all_items = self.song_list.get_children()
                if idx1 < len(all_items):
                    self.song_list.item(all_items[idx1], tags=('compare',))
                if idx2 < len(all_items):
                    self.song_list.item(all_items[idx2], tags=('compare',))
                
                self.root.after(75, self.animate_sort_step) # Jeda singkat untuk perbandingan

            elif action == 'merge':
                # Perbarui urutan treeview sesuai hasil merge
                start_index, merged_songs = args
                all_items = self.song_list.get_children()
                
                # Pindahkan item sesuai urutan baru di 'merged_songs'
                for i, song in enumerate(merged_songs):
                    current_pos = -1
                    # Cari posisi item saat ini
                    for j, item_id in enumerate(all_items):
                         values = self.song_list.item(item_id, 'values')
                         if song.title == values[0] and song.artist == values[1]:
                              current_pos = j
                              break
                    
                    if current_pos != -1:
                         # Pindahkan ke posisi yang benar dalam blok yang di-merge
                         self.song_list.move(all_items[current_pos], '', start_index + i)
                         # Tandai sebagai sudah diurutkan (dalam tahap ini)
                         self.song_list.item(all_items[current_pos], tags=('sorted',))

                self.root.after(150, self.animate_sort_step) # Jeda lebih lama untuk merge
            
        except StopIteration:
            # Animasi selesai
            self.is_sorting = False
            self.toggle_ui_state(tk.NORMAL) # Aktifkan kembali UI
            self.refresh_song_list(animate=False) # Lakukan refresh final
            self.status_bar.config(text="Pengurutan selesai.")
            self.root.after(2000, self.update_status_bar) # Kembalikan status bar setelah 2 detik

    def refresh_song_list(self, animate=True):
        """Memperbarui daftar lagu, dengan atau tanpa animasi."""
        if self.is_sorting: return

        # Jika diminta untuk animasi, panggil proses animasi
        if animate:
            self.start_sort_animation()
            return
            
        # Jika tidak, lakukan refresh instan
        self.song_list.delete(*self.song_list.get_children())
        
        # Dapatkan lagu yang sudah diurutkan (versi non-generator)
        songs = self.playlist_manager.get_sorted_playlist_songs()
        
        search_term = self.search_var.get().lower()
        
        filtered_songs = songs
        if search_term:
            filtered_songs = [
                song for song in songs 
                if (search_term in song.title.lower() or 
                    search_term in song.artist.lower() or 
                    search_term in song.album.lower())
            ]
        
        for song in filtered_songs:
            self.song_list.insert("", tk.END, values=(song.title, song.artist, song.album, song.duration))
        
        self.update_status_bar()

    def play_song(self, from_double_click=False):
        """Memutar lagu yang dipilih."""
        if self.is_sorting: return # Jangan putar lagu saat sorting

        selected_items = self.song_list.selection()
        if not selected_items:
            children = self.song_list.get_children()
            if not children:
                messagebox.showwarning("Peringatan", "Tidak ada lagu di playlist ini.")
                return
            selected_items = [children[0]]
            self.song_list.selection_set(selected_items[0])
        
        selected_item = selected_items[0]
        values = self.song_list.item(selected_item, 'values')
        
        # Gunakan lagu yang sudah diurutkan untuk mencari indeks
        all_songs = self.playlist_manager.get_sorted_playlist_songs()
        
        song_to_play = None
        actual_index = -1
        for i, song in enumerate(all_songs):
            if song.title == values[0] and song.artist == values[1] and song.album == values[2] and song.duration == values[3]:
                song_to_play = song
                actual_index = i
                break
        
        if song_to_play:
            self.playlist_manager.current_song_index = actual_index
            self.play_song_at_index(actual_index)
        else:
            if not from_double_click:
                messagebox.showerror("Error", "Lagu tidak dapat ditemukan. Coba segarkan daftar.")

    def play_song_at_index(self, index):
        """Memutar lagu berdasarkan indeks dari daftar yang sudah diurutkan."""
        songs = self.playlist_manager.get_sorted_playlist_songs()
        if not songs or not (0 <= index < len(songs)):
            self.stop_song()
            return

        song = songs[index]
        self.playlist_manager.current_song_index = index # Simpan indeks dari list yang terurut
        try:
            pygame.mixer.music.load(song.file_path)
            pygame.mixer.music.play()
            self.playlist_manager.playing = True
            self.playlist_manager.record_play(song)
            self.update_now_playing(song)
            self.playlist_manager.save_to_file("music_library.json")
            
            all_items = self.song_list.get_children()
            if index < len(all_items):
                item_to_select = all_items[index]
                self.song_list.selection_set(item_to_select)
                self.song_list.focus(item_to_select)
                self.song_list.see(item_to_select)

        except Exception as e:
            messagebox.showerror("Error", f"Tidak dapat memutar lagu: {song.file_path}\nError: {str(e)}")
            self.stop_song()
            
    def next_song(self):
        """Memutar lagu berikutnya dalam urutan saat ini."""
        if self.is_sorting: return
        songs = self.playlist_manager.get_sorted_playlist_songs()
        if not songs: return
        
        next_index = (self.playlist_manager.current_song_index + 1) % len(songs)
        self.play_song_at_index(next_index)

    def prev_song(self):
        """Memutar lagu sebelumnya dalam urutan saat ini."""
        if self.is_sorting: return
        songs = self.playlist_manager.get_sorted_playlist_songs()
        if not songs: return
        
        if pygame.mixer.music.get_pos() > 3000:
            self.play_song_at_index(self.playlist_manager.current_song_index)
        else:
            prev_index = (self.playlist_manager.current_song_index - 1 + len(songs)) % len(songs)
            self.play_song_at_index(prev_index)

    # ... (Sisa fungsi-fungsi UI lainnya tidak perlu diubah secara signifikan) ...
    # Cukup pastikan mereka tidak berjalan saat is_sorting == True
    def manage_playlists(self):
        if self.is_sorting: return
        dialog = PlaylistManagerDialog(self.root, list(self.playlist_manager.playlists.keys()))
        self.root.wait_window(dialog)
        
        if dialog.result:
            action, *args = dialog.result
            success = False
            message = ""
            if action == "create":
                if self.playlist_manager.create_playlist(args[0]):
                    success = True
                    message = f"Playlist '{args[0]}' berhasil dibuat."
            elif action == "rename":
                if self.playlist_manager.rename_playlist(args[0], args[1]):
                    success = True
                    message = f"Playlist '{args[0]}' berhasil diubah menjadi '{args[1]}'."
            elif action == "delete":
                if self.playlist_manager.delete_playlist(args[0]):
                    success = True
                    message = f"Playlist '{args[0]}' berhasil dihapus."
            
            if success:
                messagebox.showinfo("Sukses", message, parent=self.root)
                self.playlist_manager.save_to_file("music_library.json")
                self.update_playlist_dropdown()
                self.refresh_song_list(animate=False)
            else:
                messagebox.showwarning("Gagal", "Operasi playlist gagal. Nama mungkin sudah ada.", parent=self.root)

    def update_playlist_dropdown(self):
        current_selection = self.playlist_var.get()
        playlist_keys = list(self.playlist_manager.playlists.keys())
        self.playlist_dropdown['values'] = playlist_keys
        
        if current_selection in playlist_keys:
            self.playlist_var.set(current_selection)
        else:
            self.playlist_var.set(self.playlist_manager.current_playlist)

    def perform_search(self, event=None):
        if self.is_sorting: return
        self.refresh_song_list(animate=False)

    def clear_search(self):
        if self.is_sorting: return
        self.search_var.set("")
        self.refresh_song_list(animate=False)
        self.search_entry.focus()

    def update_now_playing(self, song):
        favorite_status = "⭐" if self.playlist_manager.is_favorite(song) else ""
        self.now_playing_info.config(
            text=f"{song.title} {favorite_status}\n{song.artist} — {song.album}"
        )
        self.update_album_art(song)
        
    def update_album_art(self, song):
        try:
            if song:
                audiofile = eyed3.load(song.file_path)
                if audiofile and audiofile.tag and audiofile.tag.images:
                    image_data = audiofile.tag.images[0].image_data
                    img = Image.open(io.BytesIO(image_data))
                    img.thumbnail((80, 80))
                    self.album_art_img = ImageTk.PhotoImage(img)
                    self.album_art_label.config(image=self.album_art_img)
                    return

            placeholder = Image.new('RGB', (80, 80), color = '#e0e0e0')
            self.album_art_img = ImageTk.PhotoImage(placeholder)
            self.album_art_label.config(image=self.album_art_img)
        except Exception:
            placeholder = Image.new('RGB', (80, 80), color = '#cccccc')
            self.album_art_img = ImageTk.PhotoImage(placeholder)
            self.album_art_label.config(image=self.album_art_img)

    def pause_song(self):
        if self.playlist_manager.playing:
            pygame.mixer.music.pause()
            self.playlist_manager.playing = False
        else:
            if pygame.mixer.music.get_pos() > 0:
                pygame.mixer.music.unpause()
                self.playlist_manager.playing = True

    def stop_song(self):
        pygame.mixer.music.stop()
        self.playlist_manager.playing = False
        self.now_playing_info.config(text="Pemutaran dihentikan")
        self.update_album_art(None)
        self.progress_bar['value'] = 0
        self.progress_label.config(text="00:00 / 00:00")

    def set_volume(self, val):
        volume = float(val) / 100
        pygame.mixer.music.set_volume(volume)

    def update_progress(self):
        if self.playlist_manager.playing:
            current_pos = pygame.mixer.music.get_pos() / 1000
            songs = self.playlist_manager.get_sorted_playlist_songs()
            
            if 0 <= self.playlist_manager.current_song_index < len(songs):
                song = songs[self.playlist_manager.current_song_index]
                duration_seconds = song.get_duration_seconds()
                
                if duration_seconds > 0:
                    progress = (current_pos / duration_seconds) * 100
                    self.progress_bar['value'] = progress
                    
                    current_time = time.strftime('%M:%S', time.gmtime(current_pos))
                    self.progress_label.config(text=f"{current_time} / {song.duration}")
            
            if not pygame.mixer.music.get_busy():
                self.next_song()

        self.root.after(1000, self.update_progress)

    def on_song_double_click(self, event):
        if self.is_sorting: return
        self.play_song(from_double_click=True)

    def on_closing(self):
        self.playlist_manager.save_to_file("music_library.json")
        pygame.mixer.quit()
        self.root.destroy()

    def show_stats(self):
        if self.is_sorting: return
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Statistik Musik")
        stats_window.geometry("600x400")
        stats_window.transient(self.root)
        stats_window.grab_set()

        notebook = ttk.Notebook(stats_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        most_played_frame = ttk.Frame(notebook)
        notebook.add(most_played_frame, text="Paling Sering Diputar")
        tree_most = ttk.Treeview(most_played_frame, columns=("judul", "artis", "diputar"), show="headings")
        tree_most.heading("judul", text="Judul")
        tree_most.heading("artis", text="Artis")
        tree_most.heading("diputar", text="Jumlah Diputar")
        tree_most.column("diputar", anchor=tk.E, width=100)
        for song in self.playlist_manager.get_most_played_songs(10):
            tree_most.insert("", tk.END, values=(song.title, song.artist, song.play_count))
        tree_most.pack(fill=tk.BOTH, expand=True)

        recent_frame = ttk.Frame(notebook)
        notebook.add(recent_frame, text="Baru Saja Diputar")
        tree_recent = ttk.Treeview(recent_frame, columns=("judul", "artis", "terakhir"), show="headings")
        tree_recent.heading("judul", text="Judul")
        tree_recent.heading("artis", text="Artis")
        tree_recent.heading("terakhir", text="Terakhir Diputar")
        for song in self.playlist_manager.get_recently_played(10):
            last_played_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(song.last_played)) if song.last_played else "N/A"
            tree_recent.insert("", tk.END, values=(song.title, song.artist, last_played_str))
        tree_recent.pack(fill=tk.BOTH, expand=True)

    def toggle_favorite(self):
        if self.is_sorting: return
        song, index = self.get_selected_song_from_list()
        if not song: return

        is_favorite = self.playlist_manager.toggle_favorite(song)
        self.playlist_manager.save_to_file("music_library.json")
        if self.playlist_manager.playing and self.playlist_manager.current_song_index == index:
            self.update_now_playing(song)
        
        status = "ditambahkan ke" if is_favorite else "dihapus dari"
        messagebox.showinfo("Favorit", f"Lagu '{song.title}' {status} favorit.", parent=self.root)

    def update_status_bar(self):
        if self.is_sorting: return
        current_playlist_name = self.playlist_manager.current_playlist
        songs_in_view = len(self.song_list.get_children())
        total_in_playlist = len(self.playlist_manager.playlists.get(current_playlist_name, []))
        total_library = self.playlist_manager.get_total_song_count()
        
        search_term = self.search_var.get()
        if search_term:
            status_text = f"Menampilkan {songs_in_view} lagu dari '{current_playlist_name}' (Filter: '{search_term}')  |  Total di library: {total_library} lagu"
        else:
            status_text = f"Playlist '{current_playlist_name}': {total_in_playlist} lagu  |  Total di library: {total_library} lagu"
        
        self.status_bar.config(text=status_text)
        
    def change_playlist(self, event=None):
        if self.is_sorting: return
        selected_playlist = self.playlist_var.get()
        if selected_playlist != self.playlist_manager.current_playlist:
            self.playlist_manager.current_playlist = selected_playlist
            self.playlist_manager.current_song_index = 0
            self.refresh_song_list(animate=False)
            self.stop_song()

    def add_songs(self):
        if self.is_sorting: return
        file_paths = filedialog.askopenfilenames(
            parent=self.root,
            title="Pilih File MP3",
            filetypes=[("File Audio", "*.mp3"), ("Semua File", "*.*")]
        )
        if not file_paths: return
            
        songs_added_count = 0
        for file_path in file_paths:
            try:
                audiofile = eyed3.load(file_path)
                
                title = os.path.splitext(os.path.basename(file_path))[0]
                artist = "Artis Tidak Dikenal"
                album = "Album Tidak Dikenal"
                duration_str = "00:00"

                if audiofile:
                    if audiofile.info:
                        duration_sec = audiofile.info.time_secs
                        if duration_sec:
                            duration_str = time.strftime('%M:%S', time.gmtime(duration_sec))
                    if audiofile.tag:
                        tag = audiofile.tag
                        title = tag.title or title
                        artist = tag.artist or artist
                        album = tag.album or album
                
                dialog = SongMetadataDialog(
                    self.root,
                    default_title=title, default_artist=artist, default_album=album,
                    playlists=list(self.playlist_manager.playlists.keys()),
                    current_playlist=self.playlist_manager.current_playlist
                )
                self.root.wait_window(dialog)
                
                if dialog.result:
                    song = Song(
                        title=dialog.result["title"], artist=dialog.result["artist"],
                        album=dialog.result["album"], duration=duration_str,
                        file_path=file_path, playlist=dialog.result["playlist"]
                    )
                    self.playlist_manager.add_song(song, dialog.result["playlist"])
                    songs_added_count += 1
            except Exception as e:
                messagebox.showerror("Error", f"Tidak dapat memuat {os.path.basename(file_path)}:\n{str(e)}", parent=self.root)
        
        if songs_added_count > 0:
            self.playlist_manager.save_to_file("music_library.json")
            self.refresh_song_list(animate=False)
            messagebox.showinfo("Sukses", f"Berhasil menambahkan {songs_added_count} lagu.", parent=self.root)
            
    def get_selected_song_from_list(self):
        selected_item = self.song_list.selection()
        if not selected_item:
            messagebox.showwarning("Peringatan", "Harap pilih lagu terlebih dahulu.", parent=self.root)
            return None, -1

        index_in_view = self.song_list.index(selected_item[0])
        
        songs = self.playlist_manager.get_sorted_playlist_songs()
        search_term = self.search_var.get().lower()
        if search_term:
            songs = [s for s in songs if (search_term in s.title.lower() or search_term in s.artist.lower() or search_term in s.album.lower())]

        if index_in_view < len(songs):
            return songs[index_in_view], index_in_view
        
        return None, -1

    def edit_selected_song(self):
        if self.is_sorting: return
        song, _ = self.get_selected_song_from_list()
        if not song: return
            
        dialog = SongMetadataDialog(
            self.root, default_title=song.title, default_artist=song.artist,
            default_album=song.album, playlists=list(self.playlist_manager.playlists.keys()),
            current_playlist=song.playlist
        )
        self.root.wait_window(dialog)
        
        if dialog.result:
            self.playlist_manager.update_song(song, dialog.result)
            self.playlist_manager.save_to_file("music_library.json")
            self.refresh_song_list(animate=False)
            messagebox.showinfo("Sukses", "Metadata lagu berhasil diperbarui.", parent=self.root)

    def delete_selected_song(self):
        if self.is_sorting: return
        song, _ = self.get_selected_song_from_list()
        if not song: return

        confirm = messagebox.askyesno(
            "Konfirmasi Hapus",
            f"Anda yakin ingin menghapus '{song.title}' dari library?",
            parent=self.root
        )
        if confirm:
            self.playlist_manager.delete_song(song)
            self.playlist_manager.save_to_file("music_library.json")
            self.refresh_song_list(animate=False)
            messagebox.showinfo("Sukses", "Lagu berhasil dihapus.", parent=self.root)


# ==================================================
# PROGRAM UTAMA
# ==================================================

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")
    
    app = MusicPlayerApp(root)
    root.mainloop()
