from dataclasses import dataclass, field
from pathlib import Path
from mutagen.mp3 import MP3


@dataclass
class Track:
    """Represents an audio file loaded in memory."""
    path: Path
    title: str
    duration: float

    def __post_init__(self):
        if not isinstance(self.path, Path):
            raise TypeError(f"path must be a Path object, got {type(self.path)}")
        if not isinstance(self.title, str):
            raise TypeError(f"title must be a string, got {type(self.title)}")
        if not isinstance(self.duration, (int, float)):
            raise TypeError(f"duration must be a number, got {type(self.duration)}")
        if self.duration < 0:
            raise ValueError(f"duration must be non-negative, got {self.duration}")


@dataclass
class Disc:
    """Represents a virtual CD containing multiple tracks."""
    id: int
    tracks: list[Track] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.id, int):
            raise TypeError(f"id must be an integer, got {type(self.id)}")
        if self.id < 1:
            raise ValueError(f"id must be positive, got {self.id}")
        if not isinstance(self.tracks, list):
            raise TypeError(f"tracks must be a list, got {type(self.tracks)}")
        for track in self.tracks:
            if not isinstance(track, Track):
                raise TypeError(f"All tracks must be Track objects, got {type(track)}")

    @property
    def total_seconds(self) -> float:
        return sum(t.duration for t in self.tracks)


class Splitter:
    def __init__(self, capacity_minutes: float = 79.5):
        """Initialize the Splitter with disc capacity in minutes.
        
        Args:
            capacity_minutes: Maximum capacity of each disc in minutes (default: 79.5)
            
        Raises:
            TypeError: If capacity_minutes is not a number
            ValueError: If capacity_minutes is not positive
        """
        if not isinstance(capacity_minutes, (int, float)):
            raise TypeError(f"capacity_minutes must be a number, got {type(capacity_minutes)}")
        if capacity_minutes <= 0:
            raise ValueError(f"capacity_minutes must be positive, got {capacity_minutes}")

        self.limit_seconds = capacity_minutes * 60

    def load_tracks(self, paths: list[Path]) -> list[Track]:
        """Read metadata from audio files and create Track objects.
        
        Args:
            paths: List of Path objects pointing to audio files
            
        Returns:
            List of Track objects successfully loaded
            
        Raises:
            TypeError: If paths is not a list or contains non-Path objects
        """
        if not isinstance(paths, list):
            raise TypeError(f"paths must be a list, got {type(paths)}")
        
        tracks = []
        for path in paths:
            if not isinstance(path, Path):
                print(f"⚠️ WARNING: Skipping non-Path object: {path}")
                continue
            
            if not path.exists():
                print(f"⚠️ WARNING: File does not exist: {path}")
                continue
                
            if not path.is_file():
                print(f"⚠️ WARNING: Not a file: {path}")
                continue
            
            try:
                audio = MP3(path)
                if not hasattr(audio, 'info') or not hasattr(audio.info, 'length'):
                    print(f"⚠️ WARNING: Could not read duration from {path.name}")
                    continue
                    
                track = Track(
                    path=path,
                    title=path.stem,
                    duration=audio.info.length
                )
                tracks.append(track)
            except Exception as e:
                print(f"⚠️ WARNING: Error reading {path.name}: {e}")
                continue
        return tracks

    def split_into_discs(self, tracks: list[Track]) -> list[Disc]:
        """Normal Mode (Greedy): Preserves the original order.
        
        Args:
            tracks: List of Track objects to split into discs
            
        Returns:
            List of Disc objects
            
        Raises:
            TypeError: If tracks is not a list or contains non-Track objects
        """
        if not isinstance(tracks, list):
            raise TypeError(f"tracks must be a list, got {type(tracks)}")
        
        for i, track in enumerate(tracks):
            if not isinstance(track, Track):
                raise TypeError(f"All items must be Track objects, got {type(track)} at index {i}")
        
        if not tracks:
            return []

        discs = []
        current_disc = Disc(id=1)

        for track in tracks:
            # SIZE CHECK
            if track.duration > self.limit_seconds:
                print(f"⚠️ WARNING: Track '{track.title}' ({track.duration / 60:.1f} min) exceeds disc capacity!")
                # The logic below will naturally isolate it on a new disc because it
                # won't fit on the current one, and the next one will be full with just this track.

            # Standard logic
            if current_disc.total_seconds + track.duration <= self.limit_seconds:
                current_disc.tracks.append(track)
            else:
                if current_disc.tracks:
                    discs.append(current_disc)

                current_disc = Disc(id=len(discs) + 1)
                current_disc.tracks.append(track)

        if current_disc.tracks:
            discs.append(current_disc)

        return discs

    def split_into_discs_filling_gaps(self, tracks: list[Track]) -> list[Disc]:
        """Smart Fill Mode: Fills gaps, but isolates oversized tracks.
        
        Args:
            tracks: List of Track objects to split into discs
            
        Returns:
            List of Disc objects
            
        Raises:
            TypeError: If tracks is not a list or contains non-Track objects
        """
        if not isinstance(tracks, list):
            raise TypeError(f"tracks must be a list, got {type(tracks)}")
        
        for i, track in enumerate(tracks):
            if not isinstance(track, Track):
                raise TypeError(f"All items must be Track objects, got {type(track)} at index {i}")
        
        if not tracks:
            return []

        remaining_tracks = tracks[:]
        discs = []

        while remaining_tracks:
            # If the first track in the queue is already larger than the entire CD capacity:
            if remaining_tracks[0].duration > self.limit_seconds:
                giant_track = remaining_tracks.pop(0)

                print(
                    f"⚠️ WARNING: Track '{giant_track.title}' ({giant_track.duration / 60:.1f} min) exceeds disc capacity! Will be isolated.")

                giant_disc = Disc(id=len(discs) + 1)
                giant_disc.tracks.append(giant_track)
                discs.append(giant_disc)
                continue  # Restart the loop with the next track

            # Filling Logic
            current_disc = Disc(id=len(discs) + 1)
            skipped_tracks = []

            for track in remaining_tracks:
                if current_disc.total_seconds + track.duration <= self.limit_seconds:
                    current_disc.tracks.append(track)
                else:
                    skipped_tracks.append(track)

            discs.append(current_disc)
            remaining_tracks = skipped_tracks

        return discs