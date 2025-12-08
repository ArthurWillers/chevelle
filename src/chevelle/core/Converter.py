import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Generator, Optional
from .splitter import Disc

@dataclass
class ConversionStatus:
    disc_id: int
    track_index: int
    total_tracks: int
    filename: str
    completed: bool = False
    error: Optional[str] = None

class Converter:
    def __init__(self):
        if shutil.which('ffmpeg') is None:
            raise RuntimeError("FFmpeg isn't installed.")

    def convert_batch(self, discs: list[Disc], output_dir: Path) -> Generator[ConversionStatus, None, None]:
        total_discs = len(discs)
        if total_discs < 100:
            disc_digits = 2
        elif total_discs < 1000:
            disc_digits = 3
        else:
            disc_digits = 4

        for disc in discs:
            folder_name = f"CD_{disc.id:0{disc_digits}d}"
            disc_folder = output_dir / folder_name
            disc_folder.mkdir(parents=True, exist_ok=True)
            total_tracks = len(disc.tracks)
            for i, track in enumerate(disc.tracks, start=1):
                wav_name = f"{track.title}.wav"
                full_output_path = disc_folder / wav_name
                yield ConversionStatus(
                    disc_id=disc.id,
                    track_index=i,
                    total_tracks=total_tracks,
                    filename=wav_name
                )
                success = self._run_ffmpeg(track.path, full_output_path)
                if not success:
                    print(f"Error when converting: {wav_name}")

        yield ConversionStatus(
            disc_id=0,
            track_index=0,
            total_tracks=0,
            filename="Completed.",
            completed=True
        )

    def _run_ffmpeg(self, input_path: Path, output_path: Path) -> bool:
        cmd = [
            "ffmpeg",
            "-y", "-v", "error",
            "-i", str(input_path),
            "-ar", "44100",
            "-ac", "2",
            "-f", "wav",
            "-c:a", "pcm_s16le",
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error FFmpeg ({input_path.name}): {result.stderr}")
                return False
            return True
        except Exception as e:
            print(f"Error subprocess: {e}")
            return False