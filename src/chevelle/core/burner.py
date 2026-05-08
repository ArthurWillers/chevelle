"""
Burner module - Wrapper for wodim CD burning.
Refactored for async I/O.
"""

import shutil
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import AsyncGenerator, Optional
import re


@dataclass
class BurnStatus:
    """Status update during burning process."""
    phase: str  # "preparing", "burning", "fixating", "complete", "error"
    track: int = 0
    total_tracks: int = 0
    progress: float = 0.0  # 0-100
    message: str = ""
    error: Optional[str] = None


class Burner:
    """Wrapper for wodim CD burning tool."""
    
    def __init__(self, device: str = "/dev/sr0", speed: int = 4):
        """Initialize the Burner.
        
        Args:
            device: CD/DVD drive device path
            speed: Burning speed (e.g., 4, 8, 16)
            
        Raises:
            RuntimeError: If wodim is not installed
        """
        if shutil.which('wodim') is None:
            raise RuntimeError("wodim is not installed. Please install it to continue.")
        
        self.device = device
        self.speed = speed
        self.process: Optional[asyncio.subprocess.Process] = None
        self.cancelled = False
    
    async def get_available_drives(self) -> list[str]:
        """Detect available CD/DVD drives asynchronously.
        
        Returns:
            List of device paths
        """
        drives = []
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wodim", "--devices",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10.0)
                output = stdout.decode()
                for line in output.split('\n'):
                    if '/dev/' in line:
                        match = re.search(r"(/dev/\w+)", line)
                        if match:
                            drives.append(match.group(1))
            except asyncio.TimeoutError:
                process.kill()
        except Exception:
            pass
        
        if not drives:
            common_paths = ["/dev/sr0", "/dev/sr1", "/dev/cdrom", "/dev/dvd"]
            for path in common_paths:
                if Path(path).exists():
                    drives.append(path)
        
        return drives if drives else ["/dev/sr0"]
    
    async def check_disc_status(self) -> dict:
        """Check if there's a blank disc in the drive asynchronously.
        
        Returns:
            Dict with disc status info
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "wodim", f"dev={self.device}", "-atip",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
                output = stdout.decode() + stderr.decode()
                
                is_blank = "Is erasable" in output or "Blank" in output.lower()
                is_present = "ATIP" in output or "Disc" in output
                
                disc_type = "Unknown"
                if "CD-R" in output:
                    disc_type = "CD-R"
                elif "CD-RW" in output:
                    disc_type = "CD-RW"
                
                return {
                    "present": is_present,
                    "blank": is_blank,
                    "type": disc_type,
                    "raw_output": output
                }
            except asyncio.TimeoutError:
                process.kill()
                return {"present": False, "blank": False, "type": "Unknown", "error": "Timeout"}
                
        except Exception as e:
            return {"present": False, "blank": False, "type": "Unknown", "error": str(e)}

    async def erase_disc(self) -> AsyncGenerator[BurnStatus, None]:
        """Erase a CD-RW disc in the drive asynchronously."""
        yield BurnStatus(phase="preparing", message="Checking drive for CD-RW...")
        
        disc_status = await self.check_disc_status()
        if disc_status.get("error") or not disc_status.get("present"):
            yield BurnStatus(phase="error", error="Drive check failed or no disc present.")
            return

        yield BurnStatus(phase="preparing", message=f"Erasing CD-RW on device {self.device} (fast blank)...")
        
        cmd = [
            "wodim",
            "-v",
            "blank=fast",
            f"dev={self.device}"
        ]
        
        self.cancelled = False
        
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            while True:
                if self.cancelled:
                    self.process.terminate()
                    yield BurnStatus(phase="error", error="Erase cancelled by user")
                    return
                
                line_bytes = await self.process.stdout.readline()
                if not line_bytes:
                    break
                
                line = line_bytes.decode(errors='replace').strip()
                if not line:
                    continue
                
                # Report generic progress for erase
                if "blanking" in line.lower() or "erasing" in line.lower():
                    yield BurnStatus(phase="burning", message=line, progress=50.0)
                elif "error" in line.lower() or "cannot" in line.lower() or "failed" in line.lower():
                    yield BurnStatus(phase="error", error=line)
            
            return_code = await self.process.wait()
            
            if return_code == 0:
                yield BurnStatus(phase="complete", progress=100.0, message="CD-RW successfully erased!")
            else:
                yield BurnStatus(phase="error", error=f"wodim exited with code {return_code}")
                
        except Exception as e:
            yield BurnStatus(phase="error", error=str(e))
        finally:
            self.process = None

    async def burn_disc(self, wav_files: list[Path], eject: bool = True) -> AsyncGenerator[BurnStatus, None]:
        """Burn WAV files to an audio CD using wodim asynchronously.
        
        Args:
            wav_files: List of WAV file paths (in order)
            eject: Whether to eject disc after burning
            
        Yields:
            BurnStatus objects with progress updates
        """
        self.cancelled = False
        
        if not wav_files:
            yield BurnStatus(phase="error", error="No files to burn")
            return
        
        for wav in wav_files:
            if not wav.exists():
                yield BurnStatus(phase="error", error=f"File not found: {wav}")
                return
        
        yield BurnStatus(
            phase="preparing",
            message=f"Preparing to burn {len(wav_files)} tracks..."
        )
        
        yield BurnStatus(
            phase="preparing", 
            message="Checking drive status..."
        )
        
        disc_status = await self.check_disc_status()
        if disc_status.get("error") or not disc_status.get("present") or not disc_status.get("blank"):
            err_msg = disc_status.get("error") or "No blank disc present."
            yield BurnStatus(
                phase="error",
                error=f"Drive check failed: {err_msg}"
            )
            return
        
        cmd = [
            "wodim",
            "-v",
            "-dao",
            "-pad",
            "-audio",
            f"speed={self.speed}",
            f"dev={self.device}",
        ]
        
        if eject:
            cmd.append("-eject")
        
        cmd.extend([str(f) for f in wav_files])
        
        yield BurnStatus(
            phase="preparing",
            message=f"Starting wodim: speed={self.speed}x, device={self.device}"
        )
        
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            current_track = 0
            total_tracks = len(wav_files)
            
            while True:
                if self.cancelled:
                    self.process.terminate()
                    yield BurnStatus(phase="error", error="Burning cancelled by user")
                    return
                
                line_bytes = await self.process.stdout.readline()
                if not line_bytes:
                    break
                
                line = line_bytes.decode(errors='replace').strip()
                if not line:
                    continue
                
                status = self._parse_wodim_output(line, current_track, total_tracks)
                
                if status:
                    if status.track > current_track:
                        current_track = status.track
                    yield status
            
            return_code = await self.process.wait()
            
            if return_code == 0:
                yield BurnStatus(
                    phase="complete",
                    track=total_tracks,
                    total_tracks=total_tracks,
                    progress=100.0,
                    message="Burn completed successfully!"
                )
            else:
                yield BurnStatus(
                    phase="error",
                    error=f"wodim exited with code {return_code}"
                )
                
        except Exception as e:
            yield BurnStatus(phase="error", error=str(e))
        finally:
            self.process = None
    
    def _parse_wodim_output(self, line: str, current_track: int, total_tracks: int) -> Optional[BurnStatus]:
        track_match = re.search(r"Track (\d+):\s+(\d+) of\s+(\d+) MB written", line)
        if track_match:
            track_num = int(track_match.group(1))
            written = int(track_match.group(2))
            total = int(track_match.group(3))
            
            track_progress = (written / total * 100) if total > 0 else 0
            overall_progress = ((track_num - 1) / total_tracks * 100) + (track_progress / total_tracks)
            
            return BurnStatus(
                phase="burning",
                track=track_num,
                total_tracks=total_tracks,
                progress=min(overall_progress, 99.0),
                message=f"Track {track_num}/{total_tracks}: {written}/{total} MB"
            )
        
        if "fixat" in line.lower():
            return BurnStatus(
                phase="fixating",
                track=total_tracks,
                total_tracks=total_tracks,
                progress=99.0,
                message="Fixating disc..."
            )
        
        if "starting" in line.lower() and "track" in line.lower():
            return BurnStatus(
                phase="burning",
                track=current_track + 1,
                total_tracks=total_tracks,
                progress=(current_track / total_tracks * 100),
                message=line
            )
        
        if "error" in line.lower() or "cannot" in line.lower() or "failed" in line.lower():
            error_msg = line
            if "not ready" in line.lower():
                error_msg = "Drive not ready - No disc inserted?"
            elif "errno: 5" in line.lower() or "input/output error" in line.lower():
                error_msg = "I/O Error - Check if disc is inserted and drive is working"
            elif "no disk" in line.lower() or "no disc" in line.lower():
                error_msg = "No disc in drive"
            elif "not permitted" in line.lower():
                error_msg = "Permission denied - Try running with sudo"
            elif "cannot open" in line.lower():
                error_msg = "Cannot open drive - Check device path"
            
            return BurnStatus(
                phase="error",
                error=error_msg
            )
        
        if any(kw in line.lower() for kw in ["burning", "writing", "track", "mb"]):
            return BurnStatus(
                phase="burning",
                track=current_track,
                total_tracks=total_tracks,
                message=line
            )
        
        return None
    
    def cancel(self) -> None:
        """Cancel the current burning operation."""
        self.cancelled = True
        if self.process:
            self.process.terminate()
