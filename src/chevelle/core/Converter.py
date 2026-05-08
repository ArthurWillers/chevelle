import shutil
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import AsyncGenerator, Optional
from .splitter import Disc

@dataclass
class ConversionStatus:
    disc_id: int
    track_index: int
    total_tracks: int
    filename: str
    completed: bool = False
    error: Optional[str] = None

class ConversionError(Exception):
    """Custom exception for conversion failures."""
    pass

class Converter:
    def __init__(self):
        if shutil.which('ffmpeg') is None:
            raise RuntimeError("FFmpeg isn't installed. Please install it to continue.")
        self.process = None
        self.cancelled = False

    def cancel(self):
        """Cancel the conversion and kill the ffmpeg process."""
        self.cancelled = True
        if self.process:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass

    async def convert_batch(self, discs: list[Disc], output_dir: Path, normalize: bool = False) -> AsyncGenerator[ConversionStatus, None]:
        total_discs = len(discs)
        if total_discs < 100:
            disc_digits = 2
        elif total_discs < 1000:
            disc_digits = 3
        else:
            disc_digits = 4

        for disc in discs:
            if self.cancelled:
                return
            
            folder_name = f"CD_{disc.id:0{disc_digits}d}"
            disc_folder = output_dir / folder_name
            disc_folder.mkdir(parents=True, exist_ok=True)
            total_tracks = len(disc.tracks)
            for i, track in enumerate(disc.tracks, start=1):
                if self.cancelled:
                    return
                
                wav_name = f"{track.title}.wav"
                full_output_path = disc_folder / wav_name
                
                yield ConversionStatus(
                    disc_id=disc.id,
                    track_index=i,
                    total_tracks=total_tracks,
                    filename=wav_name
                )
                
                success, error_msg = await self._run_ffmpeg(track.path, full_output_path, normalize)
                if not success:
                    yield ConversionStatus(
                        disc_id=disc.id,
                        track_index=i,
                        total_tracks=total_tracks,
                        filename=wav_name,
                        error=error_msg
                    )

        yield ConversionStatus(
            disc_id=0,
            track_index=0,
            total_tracks=0,
            filename="Completed.",
            completed=True
        )

    async def _run_ffmpeg(self, input_path: Path, output_path: Path, normalize: bool) -> tuple[bool, Optional[str]]:
        cmd = [
            "ffmpeg",
            "-y", "-v", "error",
            "-i", str(input_path),
            "-ar", "44100",
            "-ac", "2",
            "-f", "wav",
            "-c:a", "pcm_s16le"
        ]
        if normalize:
            cmd.extend(["-af", "loudnorm"])
            
        cmd.append(str(output_path))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.process = process
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                return False, error_msg
            return True, None
        except asyncio.CancelledError:
            if self.process:
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
            raise
        except Exception as e:
            return False, str(e)
