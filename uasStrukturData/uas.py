
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
# KELAS STRUKTUR DATA
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
        self.head = None    # Node pertama
        self.tail = None    # Node terakhir
        self.length = 0     # Jumlah lagu

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
        """Menambahkan lagu ke playlist tertentu"""
        if playlist is None:
            playlist = self.current_playlist
        
        # Buat playlist baru jika belum ada
        if playlist not in self.playlists:
            self.playlists[playlist] = PlaylistLinkedList()
        
        self.playlists[playlist].append(song)
        
        # Inisialisasi statistik lagu jika belum ada
        if song.file_path not in self.song_stats:
            self.song_stats[song.file_path] = {
                'play_count': 0,
                'last_played': None
            }

    def create_playlist(self, name):
        """Membuat playlist baru"""
        if name not in self.playlists:
            self.playlists[name] = PlaylistLinkedList()
            return True
        return False

    def rename_playlist(self, old_name, new_name):
        """Mengubah nama playlist"""
        if old_name in self.playlists and new_name not in self.playlists:
            self.playlists[new_name] = self.playlists.pop(old_name)
            
            # Update playlist di setiap lagu
            for song in self.playlists[new_name]:
                song.playlist = new_name
            
            # Update playlist aktif jika perlu
            if self.current_playlist == old_name:
                self.current_playlist = new_name
            return True
        return False

    def delete_playlist(self, name):
        """Menghapus playlist"""
        if name in self.playlists and name != "Default":
            # Pindahkan lagu ke playlist Default
            for song in self.playlists[name]:
                song.playlist = "Default"
                self.playlists["Default"].append(song)
            
            del self.playlists[name]
            
            # Update playlist aktif jika perlu
            if self.current_playlist == name:
                self.current_playlist = "Default"
            return True
        return False

    def update_song(self, old_song, new_song_data):
        """Memperbarui metadata lagu"""
        # Hapus lagu lama dari semua playlist
        for playlist in self.playlists.values():
            playlist.remove(old_song)
            
        # Buat playlist baru jika belum ada
        new_playlist = new_song_data.get("playlist", self.current_playlist)
        if new_playlist not in self.playlists:
            self.playlists[new_playlist] = PlaylistLinkedList()
            
        # Buat objek lagu baru dengan data yang diperbarui
        updated_song = Song(
            title=new_song_data["title"],
            artist=new_song_data["artist"],
            album=new_song_data["album"],
            duration=old_song.duration,
            file_path=old_song.file_path,
            playlist=new_playlist
        )
        
        # Pertahankan statistik pemutaran
        if old_song.file_path in self.song_stats:
            updated_song.play_count = old_song.play_count
            updated_song.last_played = old_song.last_played
            self.song_stats[updated_song.file_path] = {
                'play_count': updated_song.play_count,
                'last_played': updated_song.last_played
            }
            
        self.playlists[new_playlist].append(updated_song)

    def delete_song(self, song_to_delete):
        """Menghapus lagu dari semua playlist"""
        for playlist_name in self.playlists:
            self.playlists[playlist_name].remove(song_to_delete)
        
        # Hapus dari favorit jika ada
        if song_to_delete.file_path in self.favorite_songs:
            self.favorite_songs.remove(song_to_delete.file_path)
            
        # Hapus statistik
        if song_to_delete.file_path in self.song_stats:
            del self.song_stats[song_to_delete.file_path]

    def get_current_playlist_songs(self):
        """Mendapatkan daftar lagu di playlist aktif"""
        songs = list(self.playlists.get(self.current_playlist, PlaylistLinkedList()))
        return self.merge_sort(songs, self.sort_criteria, self.sort_order)

    def get_total_song_count(self):
        """Mendapatkan jumlah total lagu di semua playlist"""
        # PERBAIKAN: Menggunakan set untuk memastikan lagu unik dihitung sekali
        unique_songs = set()
        for playlist in self.playlists.values():
            for song in playlist:
                unique_songs.add(song.file_path)
        return len(unique_songs)

    def save_to_file(self, filename):
        """Menyimpan data ke file JSON"""
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
        """Memuat data dari file JSON"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
                # Muat semua playlist
                for playlist_name, songs_data in data.get("playlists", {}).items():
                    self.playlists[playlist_name] = PlaylistLinkedList()
                    for song_data in songs_data:
                        # PERBAIKAN: Memuat statistik dengan aman
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
                        
                        if song.file_path: # Hanya tambahkan jika path valid
                            self.playlists[playlist_name].append(song)
                        
                            # Simpan statistik
                            if song.file_path not in self.song_stats:
                                self.song_stats[song.file_path] = {
                                    'play_count': song.play_count,
                                    'last_played': song.last_played
                                }
                
                # Muat daftar favorit
                self.favorite_songs = set(data.get("favorites", []))
                self.current_playlist = data.get("current_playlist", "Default")
                
                # Pastikan playlist saat ini ada
                if self.current_playlist not in self.playlists:
                    self.current_playlist = "Default"

        except (FileNotFoundError, json.JSONDecodeError):
            self.save_to_file(filename)

    def merge_sort(self, arr, criteria, order):
        """Algoritma merge sort untuk mengurutkan lagu"""
        if len(arr) <= 1:
            return arr

        mid = len(arr) // 2
        left_half = arr[:mid]
        right_half = arr[mid:]

        left_half = self.merge_sort(left_half, criteria, order)
        right_half = self.merge_sort(right_half, criteria, order)

        return self._merge(left_half, right_half, criteria, order)

    def _merge(self, left, right, criteria, order):
        """Fungsi helper untuk merge sort"""
        merged = []
        left_idx = 0
        right_idx = 0

        while left_idx < len(left) and right_idx < len(right):
            # PERBAIKAN: Logika pengambilan nilai untuk perbandingan
            val_left, val_right = None, None

            if criteria == "duration":
                val_left = left[left_idx].get_duration_seconds()
                val_right = right[right_idx].get_duration_seconds()
            elif criteria == "play_count":
                val_left = left[left_idx].play_count
                val_right = right[right_idx].play_count
            elif criteria == "last_played":
                val_left = left[left_idx].last_played or 0
                val_right = right[right_idx].last_played or 0
            else: # Untuk title, artist, album
                val_left = getattr(left[left_idx], criteria, "").lower()
                val_right = getattr(right[right_idx], criteria, "").lower()

            # PERBAIKAN: Logika perbandingan yang lebih jelas
            if order == "ascending":
                condition = val_left < val_right
            else: # descending
                condition = val_left > val_right

            if condition:
                merged.append(left[left_idx])
                left_idx += 1
            else:
                merged.append(right[right_idx])
                right_idx += 1

        merged.extend(left[left_idx:])
        merged.extend(right[right_idx:])
        
        return merged

    def record_play(self, song):
        """Mencatat lagu yang sedang diputar"""
        song.play_count += 1
        song.last_played = time.time()
        
        # Update statistik
        if song.file_path in self.song_stats:
            self.song_stats[song.file_path]['play_count'] += 1
            self.song_stats[song.file_path]['last_played'] = song.last_played
        else:
            self.song_stats[song.file_path] = {
                'play_count': 1,
                'last_played': song.last_played
            }
        
        # Tambahkan ke riwayat pemutaran
        # Hapus duplikat jika ada
        self.recently_played = [s for s in self.recently_played if s.file_path != song.file_path]
        self.recently_played.insert(0, song)
        if len(self.recently_played) > 10:
            self.recently_played = self.recently_played[:10]

    def toggle_favorite(self, song):
        """Menandai/batalkan tanda lagu favorit"""
        if song.file_path in self.favorite_songs:
            self.favorite_songs.remove(song.file_path)
            return False
        else:
            self.favorite_songs.add(song.file_path)
            return True

    def is_favorite(self, song):
        """Memeriksa apakah lagu favorit"""
        return song.file_path in self.favorite_songs

    def get_most_played_songs(self, n=10):
        """Mendapatkan lagu yang paling sering diputar"""
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
        """Mendapatkan lagu yang baru saja diputar"""
        return self.recently_played[:n]


# ==================================================
# KELAS DIALOG GUI
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

        # Label dan input untuk judul lagu
        ttk.Label(main_frame, text="Judul:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.insert(0, default_title)
        self.title_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Label dan input untuk artis
        ttk.Label(main_frame, text="Artis:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.artist_entry = ttk.Entry(main_frame)
        self.artist_entry.insert(0, default_artist)
        self.artist_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # Label dan input untuk album
        ttk.Label(main_frame, text="Album:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.album_entry = ttk.Entry(main_frame)
        self.album_entry.insert(0, default_album)
        self.album_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        # Dropdown untuk memilih playlist
        ttk.Label(main_frame, text="Playlist:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.playlist_var = tk.StringVar(value=current_playlist)
        self.playlist_dropdown = ttk.Combobox(main_frame, 
                                              textvariable=self.playlist_var,
                                              values=playlists,
                                              state="readonly")
        self.playlist_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        # Frame untuk tombol
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=15)
        
        # Tombol OK dan Cancel
        ttk.Button(button_frame, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Batal", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        main_frame.grid_columnconfigure(1, weight=1)

    def on_ok(self):
        """Handler ketika tombol OK diklik"""
        self.result = {
            "title": self.title_entry.get() or "Unknown Title",
            "artist": self.artist_entry.get() or "Unknown Artist",
            "album": self.album_entry.get() or "Unknown Album",
            "playlist": self.playlist_var.get()
        }
        self.destroy()

# ... (Kelas PlaylistManagerDialog tetap sama, tidak perlu diubah) ...
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

        # Frame untuk membuat playlist baru
        create_frame = ttk.LabelFrame(main_frame, text="Buat Playlist Baru", padding=10)
        create_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.new_playlist_name = tk.StringVar()
        ttk.Entry(create_frame, textvariable=self.new_playlist_name).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(create_frame, text="Buat", command=self.create_playlist).pack(side=tk.LEFT)
        
        # Frame untuk mengganti nama playlist
        rename_frame = ttk.LabelFrame(main_frame, text="Ganti Nama Playlist", padding=10)
        rename_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.rename_old = tk.StringVar()
        self.rename_new = tk.StringVar()
        
        ttk.Label(rename_frame, text="Playlist Lama:").pack(anchor='w')
        ttk.Combobox(rename_frame, 
                     textvariable=self.rename_old,
                     values=list(current_playlists),
                     state="readonly").pack(fill=tk.X, pady=(0,5))
        ttk.Label(rename_frame, text="Nama Baru:").pack(anchor='w')
        ttk.Entry(rename_frame, textvariable=self.rename_new).pack(fill=tk.X)
        ttk.Button(rename_frame, text="Ganti Nama", command=self.rename_playlist).pack(pady=(10,0))
        
        # Frame untuk menghapus playlist
        delete_frame = ttk.LabelFrame(main_frame, text="Hapus Playlist", padding=10)
        delete_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.delete_name = tk.StringVar()
        ttk.Combobox(delete_frame, 
                     textvariable=self.delete_name,
                     values=[p for p in current_playlists if p != "Default"],
                     state="readonly").pack(fill=tk.X)
        ttk.Button(delete_frame, text="Hapus", command=self.delete_playlist).pack(pady=(10,0))
        
        # Tombol tutup
        ttk.Button(main_frame, text="Tutup", command=self.destroy).pack(pady=10, side=tk.BOTTOM)

    def create_playlist(self):
        """Membuat playlist baru"""
        name = self.new_playlist_name.get().strip()
        if name and name not in self.current_playlists:
            self.result = ("create", name)
            self.destroy()
        elif not name:
            messagebox.showwarning("Peringatan", "Harap masukkan nama playlist", parent=self)
        else:
            messagebox.showwarning("Peringatan", "Playlist sudah ada", parent=self)

    def rename_playlist(self):
        """Mengganti nama playlist"""
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
        """Menghapus playlist"""
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
        self.root.title("Pemutar Musik")
        self.root.geometry("950x700")
        
        self.playlist_manager = PlaylistManager()
        self.playlist_manager.load_from_file("music_library.json")
        
        # PERBAIKAN: Mapping dari nama tampilan ke nama atribut internal
        self.sort_criteria_map = {
            "Judul": "title",
            "Artis": "artist",
            "Album": "album",
            "Durasi": "duration",
            "Jumlah Diputar": "play_count",
            "Terakhir Diputar": "last_played"
        }
        self.sort_order_map = {"Naik": "ascending", "Turun": "descending"}
        
        self.setup_ui()
        self.update_playlist_dropdown()
        self.refresh_song_list() # Ini juga akan memanggil update_status_bar
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """Mengatur antarmuka pengguna"""
        # --- Frame Atas (Kontrol Utama) ---
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        # Kontrol Pemutaran
        playback_frame = ttk.LabelFrame(top_frame, text="Kontrol", padding=5)
        playback_frame.pack(side=tk.LEFT, padx=(0, 10), fill=tk.Y)
        ttk.Button(playback_frame, text="◀◀ Prev", command=self.prev_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_frame, text="▶ Play", command=self.play_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_frame, text="❚❚ Pause", command=self.pause_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_frame, text="■ Stop", command=self.stop_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(playback_frame, text="▶▶ Next", command=self.next_song).pack(side=tk.LEFT, padx=2)

        # Kontrol Playlist & Pencarian
        manage_frame = ttk.LabelFrame(top_frame, text="Manajemen", padding=5)
        manage_frame.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(manage_frame, text="Playlist:").pack(side=tk.LEFT, padx=(5,2))
        self.playlist_var = tk.StringVar()
        self.playlist_dropdown = ttk.Combobox(manage_frame, textvariable=self.playlist_var, state="readonly", width=15)
        self.playlist_dropdown.pack(side=tk.LEFT)
        self.playlist_dropdown.bind("<<ComboboxSelected>>", self.change_playlist)
        ttk.Button(manage_frame, text="Kelola", command=self.manage_playlists).pack(side=tk.LEFT, padx=(5,10))
        
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(manage_frame, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=tk.LEFT)
        self.search_entry.bind("<KeyRelease>", self.perform_search) # Cari saat mengetik
        ttk.Button(manage_frame, text="✖", command=self.clear_search, width=2).pack(side=tk.LEFT, padx=2)
        
        # Kontrol Volume
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
        self.sort_criteria = ttk.Combobox(sort_frame, textvariable=self.sort_criteria_var, values=list(self.sort_criteria_map.keys()), state="readonly", width=15)
        self.sort_criteria.pack(side=tk.LEFT, padx=5)
        self.sort_criteria.bind("<<ComboboxSelected>>", self.set_sort_options)
        
        self.sort_order_var = tk.StringVar(value="Naik")
        self.sort_order = ttk.Combobox(sort_frame, textvariable=self.sort_order_var, values=list(self.sort_order_map.keys()), state="readonly", width=8)
        self.sort_order.pack(side=tk.LEFT)
        self.sort_order.bind("<<ComboboxSelected>>", self.set_sort_options)

        self.song_list = ttk.Treeview(list_frame, columns=("judul", "artis", "album", "durasi"), show="headings")
        self.song_list.heading("judul", text="Judul")
        self.song_list.heading("artis", text="Artis")
        self.song_list.heading("album", text="Album")
        self.song_list.heading("durasi", text="Durasi")
        self.song_list.column("judul", width=300)
        self.song_list.column("artis", width=200)
        self.song_list.column("album", width=200)
        self.song_list.column("durasi", width=80, anchor=tk.E)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.song_list.yview)
        self.song_list.configure(yscrollcommand=scrollbar.set)
        
        self.song_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.song_list.bind("<Double-1>", self.on_song_double_click)
        
        # --- Frame Bawah (Now Playing & Progress) ---
        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill=tk.X)

        self.album_art_img = None # Referensi gambar
        self.album_art_label = ttk.Label(bottom_frame, text="Album Art")
        self.album_art_label.pack(side=tk.LEFT, padx=(0, 10))
        self.update_album_art(None) # Set placeholder
        
        info_progress_frame = ttk.Frame(bottom_frame)
        info_progress_frame.pack(fill=tk.X, expand=True)

        self.now_playing_info = ttk.Label(info_progress_frame, text="Tidak ada lagu yang diputar", wraplength=600, font=("Segoe UI", 10))
        self.now_playing_info.pack(fill=tk.X, anchor='w')
        
        self.progress_bar = ttk.Progressbar(info_progress_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress_bar.pack(fill=tk.X, expand=True, pady=5)
        self.progress_label = ttk.Label(info_progress_frame, text="00:00 / 00:00")
        self.progress_label.pack(fill=tk.X, anchor='e')
        
        # Tombol Aksi
        action_frame = ttk.Frame(info_progress_frame)
        action_frame.pack(fill=tk.X, pady=(5,0))
        ttk.Button(action_frame, text="➕ Tambah Lagu", command=self.add_songs).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="✏️ Edit Lagu", command=self.edit_selected_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="❌ Hapus Lagu", command=self.delete_selected_song).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="⭐ Favorit", command=self.toggle_favorite).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="📊 Statistik", command=self.show_stats).pack(side=tk.LEFT, padx=2)
        
        # --- FITUR BARU: Status Bar ---
        self.status_bar = ttk.Label(self.root, text="Memuat...", anchor=tk.W, relief=tk.SUNKEN, padding=2)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.update_progress()
        
    def manage_playlists(self):
        """Menampilkan dialog manajemen playlist"""
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
                self.refresh_song_list()
            else:
                messagebox.showwarning("Gagal", "Operasi playlist gagal. Nama mungkin sudah ada.", parent=self.root)

    def update_playlist_dropdown(self):
        """Memperbarui daftar playlist di dropdown"""
        current_selection = self.playlist_var.get()
        playlist_keys = list(self.playlist_manager.playlists.keys())
        self.playlist_dropdown['values'] = playlist_keys
        
        if current_selection in playlist_keys:
            self.playlist_var.set(current_selection)
        else:
            self.playlist_var.set(self.playlist_manager.current_playlist)

    def perform_search(self, event=None):
        """Melakukan pencarian lagu secara dinamis"""
        self.refresh_song_list()

    def clear_search(self):
        """Menghapus hasil pencarian"""
        self.search_var.set("")
        self.refresh_song_list()
        self.search_entry.focus()

    def play_song(self, from_double_click=False):
        """Memutar lagu yang dipilih"""
        selected_items = self.song_list.selection()
        if not selected_items:
            # Jika tidak ada yang dipilih, coba mainkan lagu pertama di list
            children = self.song_list.get_children()
            if not children:
                messagebox.showwarning("Peringatan", "Tidak ada lagu di playlist ini.")
                return
            selected_items = [children[0]]
            self.song_list.selection_set(selected_items[0])
        
        selected_item = selected_items[0]
        # Dapatkan nilai dari Treeview
        values = self.song_list.item(selected_item, 'values')
        
        # Dapatkan daftar lagu yang diurutkan saat ini
        all_songs = self.playlist_manager.get_current_playlist_songs()
        
        # Cari lagu yang sesuai di daftar lagu yang sudah diurutkan
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
            if not from_double_click: # Hindari pesan error ganda
                messagebox.showerror("Error", "Lagu tidak dapat ditemukan. Coba segarkan daftar.")

    def play_song_at_index(self, index):
        """Memutar lagu berdasarkan indeks"""
        songs = self.playlist_manager.get_current_playlist_songs()
        if not songs or not (0 <= index < len(songs)):
            self.stop_song()
            return

        song = songs[index]
        try:
            pygame.mixer.music.load(song.file_path)
            pygame.mixer.music.play()
            self.playlist_manager.playing = True
            self.playlist_manager.record_play(song)
            self.update_now_playing(song)
            self.playlist_manager.save_to_file("music_library.json")
            
            # Sorot lagu yang sedang diputar di Treeview
            all_items = self.song_list.get_children()
            if index < len(all_items):
                item_to_select = all_items[index]
                self.song_list.selection_set(item_to_select)
                self.song_list.focus(item_to_select)
                self.song_list.see(item_to_select)

        except Exception as e:
            messagebox.showerror("Error", f"Tidak dapat memutar lagu: {song.file_path}\nError: {str(e)}")
            self.stop_song()
            
    def update_now_playing(self, song):
        """Memperbarui info lagu yang sedang diputar"""
        favorite_status = "⭐" if self.playlist_manager.is_favorite(song) else ""
        self.now_playing_info.config(
            text=f"{song.title} {favorite_status}\n{song.artist} — {song.album}"
        )
        self.update_album_art(song)
        
    def update_album_art(self, song):
        """Memperbarui gambar album art"""
        try:
            if song:
                audiofile = eyed3.load(song.file_path)
                if audiofile and audiofile.tag and audiofile.tag.images:
                    image_data = audiofile.tag.images[0].image_data
                    img = Image.open(io.BytesIO(image_data))
                    img.thumbnail((80, 80)) # Ukuran yang lebih sesuai
                    self.album_art_img = ImageTk.PhotoImage(img)
                    self.album_art_label.config(image=self.album_art_img)
                    return

            # Jika tidak ada lagu atau tidak ada album art, tampilkan placeholder
            placeholder = Image.new('RGB', (80, 80), color = '#e0e0e0')
            self.album_art_img = ImageTk.PhotoImage(placeholder)
            self.album_art_label.config(image=self.album_art_img)
        except Exception:
            # Handle error saat memuat gambar
            placeholder = Image.new('RGB', (80, 80), color = '#cccccc')
            self.album_art_img = ImageTk.PhotoImage(placeholder)
            self.album_art_label.config(image=self.album_art_img)

    def pause_song(self):
        """Menjeda atau melanjutkan pemutaran"""
        if self.playlist_manager.playing:
            pygame.mixer.music.pause()
            self.playlist_manager.playing = False
        else:
            if pygame.mixer.music.get_pos() > 0:
                pygame.mixer.music.unpause()
                self.playlist_manager.playing = True

    def stop_song(self):
        """Menghentikan pemutaran"""
        pygame.mixer.music.stop()
        self.playlist_manager.playing = False
        self.now_playing_info.config(text="Pemutaran dihentikan")
        self.update_album_art(None)
        self.progress_bar['value'] = 0
        self.progress_label.config(text="00:00 / 00:00")

    def next_song(self):
        """Memutar lagu berikutnya"""
        songs = self.playlist_manager.get_current_playlist_songs()
        if not songs: return
        
        next_index = (self.playlist_manager.current_song_index + 1) % len(songs)
        self.play_song_at_index(next_index)

    def prev_song(self):
        """Memutar lagu sebelumnya"""
        songs = self.playlist_manager.get_current_playlist_songs()
        if not songs: return
            
        # Kembali ke awal lagu jika sudah diputar > 3 detik
        if pygame.mixer.music.get_pos() > 3000:
            self.play_song_at_index(self.playlist_manager.current_song_index)
        else:
            prev_index = (self.playlist_manager.current_song_index - 1 + len(songs)) % len(songs)
            self.play_song_at_index(prev_index)

    def set_volume(self, val):
        """Mengatur volume pemutaran"""
        volume = float(val) / 100
        pygame.mixer.music.set_volume(volume)

    def update_progress(self):
        """Memperbarui progress bar pemutaran"""
        if self.playlist_manager.playing:
            current_pos = pygame.mixer.music.get_pos() / 1000
            songs = self.playlist_manager.get_current_playlist_songs()
            
            if 0 <= self.playlist_manager.current_song_index < len(songs):
                song = songs[self.playlist_manager.current_song_index]
                duration_seconds = song.get_duration_seconds()
                
                if duration_seconds > 0:
                    progress = (current_pos / duration_seconds) * 100
                    self.progress_bar['value'] = progress
                    
                    current_time = time.strftime('%M:%S', time.gmtime(current_pos))
                    self.progress_label.config(text=f"{current_time} / {song.duration}")
            
            # Cek jika lagu selesai
            if not pygame.mixer.music.get_busy():
                self.next_song()

        self.root.after(1000, self.update_progress)

    def on_song_double_click(self, event):
        """Handler ketika lagu diklik dua kali"""
        self.play_song(from_double_click=True)

    def on_closing(self):
        """Handler ketika aplikasi ditutup"""
        self.playlist_manager.save_to_file("music_library.json")
        pygame.mixer.quit()
        self.root.destroy()

    def show_stats(self):
        """Menampilkan statistik pemutaran"""
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Statistik Musik")
        stats_window.geometry("600x400")
        stats_window.transient(self.root)
        stats_window.grab_set()

        notebook = ttk.Notebook(stats_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab Paling Sering Diputar
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

        # Tab Baru Saja Diputar
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
        """Menandai atau menghapus tanda favorit pada lagu"""
        selected_item = self.song_list.selection()
        if not selected_item: return

        index = self.song_list.index(selected_item[0])
        songs = self.playlist_manager.get_current_playlist_songs()
        
        if index < len(songs):
            song = songs[index]
            is_favorite = self.playlist_manager.toggle_favorite(song)
            self.playlist_manager.save_to_file("music_library.json")
            # Perbarui info 'now playing' jika lagu yang sama sedang diputar
            if self.playlist_manager.playing and self.playlist_manager.current_song_index == index:
                self.update_now_playing(song)
            
            status = "ditambahkan ke" if is_favorite else "dihapus dari"
            messagebox.showinfo("Favorit", f"Lagu '{song.title}' {status} favorit.", parent=self.root)

    def set_sort_options(self, event=None):
        """PERBAIKAN: Mengatur kriteria dan urutan pengurutan lalu menyegarkan daftar"""
        selected_criteria_display = self.sort_criteria_var.get()
        selected_order_display = self.sort_order_var.get()

        self.playlist_manager.sort_criteria = self.sort_criteria_map[selected_criteria_display]
        self.playlist_manager.sort_order = self.sort_order_map[selected_order_display]
        
        self.refresh_song_list()

    def refresh_song_list(self):
        """Memperbarui daftar lagu yang ditampilkan berdasarkan filter dan urutan"""
        self.song_list.delete(*self.song_list.get_children())
        songs = self.playlist_manager.get_current_playlist_songs()
        
        search_term = self.search_var.get().lower()
        
        # Filter berdasarkan pencarian
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

    def update_status_bar(self):
        """FITUR BARU: Memperbarui teks pada status bar"""
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
        """Mengganti playlist yang aktif"""
        selected_playlist = self.playlist_var.get()
        if selected_playlist != self.playlist_manager.current_playlist:
            self.playlist_manager.current_playlist = selected_playlist
            self.playlist_manager.current_song_index = 0
            self.refresh_song_list()
            self.stop_song()

    def add_songs(self):
        """Menambahkan lagu baru ke aplikasi"""
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
                
                # Default values
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
            self.refresh_song_list()
            messagebox.showinfo("Sukses", f"Berhasil menambahkan {songs_added_count} lagu.", parent=self.root)
            
    def get_selected_song_from_list(self):
        """Helper untuk mendapatkan objek lagu dari item yang dipilih di Treeview"""
        selected_item = self.song_list.selection()
        if not selected_item:
            messagebox.showwarning("Peringatan", "Harap pilih lagu terlebih dahulu.", parent=self.root)
            return None, -1

        index_in_view = self.song_list.index(selected_item[0])
        all_songs_in_view = self.song_list.get_children()
        
        values = self.song_list.item(all_songs_in_view[index_in_view], 'values')

        # Dapatkan daftar lagu yang diurutkan/difilter yang sama dengan yang ditampilkan
        songs = self.playlist_manager.get_current_playlist_songs()
        search_term = self.search_var.get().lower()
        if search_term:
            songs = [s for s in songs if (search_term in s.title.lower() or search_term in s.artist.lower() or search_term in s.album.lower())]

        if index_in_view < len(songs):
            return songs[index_in_view], index_in_view
        
        return None, -1


    def edit_selected_song(self):
        """Mengedit metadata lagu yang dipilih"""
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
            self.refresh_song_list()
            messagebox.showinfo("Sukses", "Metadata lagu berhasil diperbarui.", parent=self.root)

    def delete_selected_song(self):
        """Menghapus lagu yang dipilih"""
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
            self.refresh_song_list()
            messagebox.showinfo("Sukses", "Lagu berhasil dihapus.", parent=self.root)


# ==================================================
# PROGRAM UTAMA
# ==================================================

if __name__ == "__main__":
    root = tk.Tk()
    # Menggunakan tema yang lebih modern jika tersedia
    style = ttk.Style(root)
    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")
    
    app = MusicPlayerApp(root)
    root.mainloop()

