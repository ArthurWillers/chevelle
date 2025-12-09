"""
Burner module - Wrapper for wodim CD burning.
"""

import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Generator, Optional
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
            raise RuntimeError("wodim is not installed. Install it with: sudo apt install wodim")
        
        self.device = device
        self.speed = speed
        self.process: Optional[subprocess.Popen] = None
        self.cancelled = False
    
    def get_available_drives(self) -> list[str]:
        """Detect available CD/DVD drives.
        
        Returns:
            List of device paths
        """
        drives = []
        
        # Try wodim --devices
        try:
            result = subprocess.run(
                ["wodim", "--devices"],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Parse output for device paths
            for line in result.stdout.split('\n'):
                if '/dev/' in line:
                    match = re.search(r"(/dev/\w+)", line)
                    if match:
                        drives.append(match.group(1))
        except Exception:
            pass
        
        # Fallback: check common device paths
        if not drives:
            common_paths = ["/dev/sr0", "/dev/sr1", "/dev/cdrom", "/dev/dvd"]
            for path in common_paths:
                if Path(path).exists():
                    drives.append(path)
        
        return drives if drives else ["/dev/sr0"]
    
    def check_disc_status(self) -> dict:
        """Check if there's a blank disc in the drive.
        
        Returns:
            Dict with disc status info
        """
        try:
            result = subprocess.run(
                ["wodim", f"dev={self.device}", "-atip"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            
            is_blank = "Is erasable" in output or "Blank" in output.lower()
            is_present = "ATIP" in output or "Disc" in output
            
            # Try to get disc type
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
        except subprocess.TimeoutExpired:
            return {"present": False, "blank": False, "type": "Unknown", "error": "Timeout"}
        except Exception as e:
            return {"present": False, "blank": False, "type": "Unknown", "error": str(e)}
    
    def burn_disc(self, wav_files: list[Path], eject: bool = True) -> Generator[BurnStatus, None, None]:
        """Burn WAV files to an audio CD using wodim.
        
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
        
        # Validate files exist
        for wav in wav_files:
            if not wav.exists():
                yield BurnStatus(phase="error", error=f"File not found: {wav}")
                return
        
        yield BurnStatus(
            phase="preparing",
            message=f"Preparing to burn {len(wav_files)} tracks..."
        )
        
        # Check disc status first
        yield BurnStatus(
            phase="preparing", 
            message="Checking drive status..."
        )
        
        disc_status = self.check_disc_status()
        if disc_status.get("error"):
            yield BurnStatus(
                phase="error",
                error=f"Drive check failed: {disc_status.get('error')}"
            )
            return
        
        # Build wodim command
        # wodim -v -eject -dao -pad -audio speed=4 dev=/dev/sr0 file1.wav file2.wav...
        cmd = [
            "wodim",
            "-v",                      # Verbose output
            "-dao",                    # Disk At Once mode
            "-pad",                    # Pad tracks to multiple of 2352 bytes
            "-audio",                  # Audio CD mode
            f"speed={self.speed}",     # Burning speed
            f"dev={self.device}",      # Device
        ]
        
        if eject:
            cmd.append("-eject")
        
        # Add all WAV files
        cmd.extend([str(f) for f in wav_files])
        
        yield BurnStatus(
            phase="preparing",
            message=f"Starting wodim: speed={self.speed}x, device={self.device}"
        )
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            current_track = 0
            total_tracks = len(wav_files)
            
            for line in iter(self.process.stdout.readline, ''):
                if self.cancelled:
                    self.process.terminate()
                    yield BurnStatus(phase="error", error="Burning cancelled by user")
                    return
                
                line = line.strip()
                if not line:
                    continue
                
                # Parse wodim output for progress
                status = self._parse_wodim_output(line, current_track, total_tracks)
                
                if status:
                    if status.track > current_track:
                        current_track = status.track
                    yield status
            
            # Wait for process to complete
            return_code = self.process.wait()
            
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
        """Parse a line of wodim output and return status if relevant.
        
        Args:
            line: Output line from wodim
            current_track: Current track being burned
            total_tracks: Total number of tracks
            
        Returns:
            BurnStatus if the line contains progress info, None otherwise
        """
        # Track progress: "Track 01:   12 of   45 MB written (fifo 100%) [buf  99%]   4.0x."
        track_match = re.search(r"Track (\d+):\s+(\d+) of\s+(\d+) MB written", line)
        if track_match:
            track_num = int(track_match.group(1))
            written = int(track_match.group(2))
            total = int(track_match.group(3))
            
            # Calculate overall progress
            track_progress = (written / total * 100) if total > 0 else 0
            overall_progress = ((track_num - 1) / total_tracks * 100) + (track_progress / total_tracks)
            
            return BurnStatus(
                phase="burning",
                track=track_num,
                total_tracks=total_tracks,
                progress=min(overall_progress, 99.0),
                message=f"Track {track_num}/{total_tracks}: {written}/{total} MB"
            )
        
        # Fixating: "Fixating..."
        if "fixat" in line.lower():
            return BurnStatus(
                phase="fixating",
                track=total_tracks,
                total_tracks=total_tracks,
                progress=99.0,
                message="Fixating disc..."
            )
        
        # Starting track: "Starting new track"
        if "starting" in line.lower() and "track" in line.lower():
            return BurnStatus(
                phase="burning",
                track=current_track + 1,
                total_tracks=total_tracks,
                progress=(current_track / total_tracks * 100),
                message=line
            )
        
        # Errors
        if "error" in line.lower() or "cannot" in line.lower() or "failed" in line.lower():
            # Parse specific error types
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
        
        # Generic progress message
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
